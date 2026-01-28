#!/usr/bin/env python3
"""
Link unmatched CUSTOMER DEPOSITS to charters via:
1. Square payment ID matching (Square, Inc. receipts)
2. Customer name fuzzy matching (e-transfer receipts)

This handles the 2,972 unlinked CUSTOMER DEPOSITS ($3.9M).
"""
import os
import re
import sys
from difflib import SequenceMatcher
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def clean_name(name):
    """Remove special chars and normalize for fuzzy matching"""
    if not name:
        return ""
    # Remove numbers, keep only letters and spaces
    cleaned = re.sub(r'[^a-zA-Z\s]', '', name.upper())
    # Collapse whitespace
    cleaned = ' '.join(cleaned.split())
    return cleaned

def extract_name_from_etransfer(description):
    """Extract customer name from e-transfer description"""
    if not description:
        return None
    
    # Pattern: "Internet Banking E-TRANSFER 105763407934 DAVID WILLIAM RICHARD"
    # or: "Internet Banking E-TRANSFER105763407934 DAVIDRICHARD"
    match = re.search(r'E-TRANSFER\s*\d+\s+(.+?)(?:\s+\d{4}\*|$)', description, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        return clean_name(name)
    
    return None

def fuzzy_match_name(target, candidates, threshold=0.80):
    """Find best fuzzy match for target name in candidates"""
    if not target:
        return None
    
    target_clean = clean_name(target)
    best_match = None
    best_score = 0
    
    for candidate_id, candidate_name in candidates:
        candidate_clean = clean_name(candidate_name)
        if not candidate_clean:
            continue
        
        score = SequenceMatcher(None, target_clean, candidate_clean).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = (candidate_id, candidate_name, score)
    
    return best_match

def main():
    apply_mode = ('--apply' in sys.argv or '--yes' in sys.argv)
    dry_run = ('--dry-run' in sys.argv)
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get unlinked CUSTOMER DEPOSITS
    print("Loading unlinked CUSTOMER DEPOSITS...")
    cur.execute("""
        SELECT receipt_id, receipt_date, revenue, description, banking_transaction_id
        FROM receipts
        WHERE revenue > 0
        AND vendor_name ILIKE '%customer%deposit%'
        AND reserve_number IS NULL
        AND charter_id IS NULL
        ORDER BY receipt_date DESC
    """)
    
    receipts = cur.fetchall()
    print(f"Found {len(receipts):,} unlinked CUSTOMER DEPOSITS (${sum(r[2] for r in receipts):,.2f})")
    
    # Categorize receipts
    square_receipts = []
    etransfer_receipts = []
    other_receipts = []
    
    for receipt_id, date, revenue, description, banking_tx_id in receipts:
        if 'Square, Inc' in description:
            square_receipts.append((receipt_id, date, revenue, description, banking_tx_id))
        elif 'E-TRANSFER' in description:
            name = extract_name_from_etransfer(description)
            if name:
                etransfer_receipts.append((receipt_id, date, revenue, description, banking_tx_id, name))
            else:
                other_receipts.append((receipt_id, date, revenue, description))
        else:
            other_receipts.append((receipt_id, date, revenue, description))
    
    print(f"\nCategorization:")
    print(f"  - Square receipts: {len(square_receipts):,} (${sum(r[2] for r in square_receipts):,.2f})")
    print(f"  - E-transfer receipts: {len(etransfer_receipts):,} (${sum(r[2] for r in etransfer_receipts):,.2f})")
    print(f"  - Other receipts: {len(other_receipts):,} (${sum(r[2] for r in other_receipts):,.2f})")
    
    # Match Square receipts by amount and date
    print("\n" + "="*80)
    print("MATCHING SQUARE RECEIPTS")
    print("="*80)
    
    square_matches = []
    square_amount_lookup = {}
    
    # Build Square payment lookup by date+amount
    cur.execute("""
        SELECT payment_id, payment_date, amount, square_payment_id, reserve_number
        FROM payments
        WHERE payment_method = 'credit_card'
        AND square_payment_id IS NOT NULL
    """)
    
    for payment_id, payment_date, amount, square_id, reserve_number in cur.fetchall():
        key = (payment_date, float(amount))
        if key not in square_amount_lookup:
            square_amount_lookup[key] = []
        square_amount_lookup[key].append({
            'payment_id': payment_id,
            'square_id': square_id,
            'reserve_number': reserve_number
        })
    
    print(f"Built lookup with {len(square_amount_lookup):,} unique Square date+amount combinations")
    
    # Match Square receipts
    for receipt_id, date, revenue, description, banking_tx_id in square_receipts:
        key = (date, float(revenue))
        if key in square_amount_lookup:
            payments = square_amount_lookup[key]
            if len(payments) == 1:
                payment = payments[0]
                if payment['reserve_number']:
                    # Get charter_id
                    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (payment['reserve_number'],))
                    charter = cur.fetchone()
                    if charter:
                        square_matches.append({
                            'receipt_id': receipt_id,
                            'reserve_number': payment['reserve_number'],
                            'charter_id': charter[0],
                            'payment_id': payment['payment_id'],
                            'match_method': 'square_date_amount'
                        })
                    else:
                        print(f"  WARNING: Reserve {payment['reserve_number']} not found in charters")
                else:
                    print(f"  WARNING: Square payment {payment['payment_id']} has no reserve_number")
            elif len(payments) > 1:
                print(f"  WARNING: Multiple Square payments for {date} ${revenue:,.2f}")
    
    print(f"Matched {len(square_matches):,} Square receipts")
    
    # Match e-transfer receipts by customer name
    print("\n" + "="*80)
    print("MATCHING E-TRANSFER RECEIPTS")
    print("="*80)
    
    # Build payment lookup by customer name
    cur.execute("""
        SELECT p.payment_id, p.payment_date, p.amount, p.reserve_number, 
               COALESCE(p.square_customer_name, c.client_name, c.company_name) as customer_name
        FROM payments p
        LEFT JOIN charters ch ON p.reserve_number = ch.reserve_number
        LEFT JOIN clients c ON ch.client_id = c.client_id
        WHERE p.reserve_number IS NOT NULL
    """)
    
    payment_names = []
    for payment_id, payment_date, amount, reserve_number, customer_name in cur.fetchall():
        if customer_name:
            payment_names.append((payment_id, customer_name, payment_date, amount, reserve_number))
    
    print(f"Built lookup with {len(payment_names):,} payments with customer names")
    
    etransfer_matches = []
    no_match_count = 0
    
    for receipt_id, date, revenue, description, banking_tx_id, name in etransfer_receipts:
        # Build candidates (payments within ±5 days, amount within ±10%)
        candidates = []
        for payment_id, customer_name, payment_date, amount, reserve_number in payment_names:
            date_diff = abs((date - payment_date).days)
            amount_diff = abs(float(revenue) - float(amount)) / float(amount) if amount else 1.0
            
            if date_diff <= 5 and amount_diff <= 0.10:
                candidates.append((payment_id, customer_name, reserve_number))
        
        if candidates:
            match = fuzzy_match_name(name, [(c[0], c[1]) for c in candidates], threshold=0.75)
            if match:
                payment_id, matched_name, score = match
                reserve_number = next(c[2] for c in candidates if c[0] == payment_id)
                
                # Get charter_id
                cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_number,))
                charter = cur.fetchone()
                
                if charter:
                    etransfer_matches.append({
                        'receipt_id': receipt_id,
                        'reserve_number': reserve_number,
                        'charter_id': charter[0],
                        'payment_id': payment_id,
                        'match_method': f'etransfer_name_fuzzy_{score:.2f}'
                    })
                else:
                    print(f"  WARNING: Reserve {reserve_number} not found in charters")
            else:
                no_match_count += 1
        else:
            no_match_count += 1
    
    print(f"Matched {len(etransfer_matches):,} e-transfer receipts")
    print(f"No match: {no_match_count:,} e-transfer receipts")
    
    # Summary
    all_matches = square_matches + etransfer_matches
    print("\n" + "="*80)
    print(f"TOTAL MATCHES: {len(all_matches):,}")
    print(f"  - Square: {len(square_matches):,}")
    print(f"  - E-transfer: {len(etransfer_matches):,}")
    print("="*80)
    
    if len(all_matches) == 0:
        print("\nNo matches found.")
        cur.close()
        conn.close()
        return
    
    # Show samples
    print(f"\nSample matches (first 10):")
    for m in all_matches[:10]:
        print(f"  Receipt {m['receipt_id']} → Reserve {m['reserve_number']} (via {m['match_method']})")
    
    # Apply updates
    print("\n" + "="*80)
    if not apply_mode:
        print(f"Dry-run: would update {len(all_matches):,} receipts. Pass --apply to execute.")
        cur.close()
        conn.close()
        return
    
    print("\nApplying updates...")
    for match in all_matches:
        cur.execute("""
            UPDATE receipts
            SET reserve_number = %s, 
                charter_id = %s
            WHERE receipt_id = %s
            AND reserve_number IS NULL
            AND charter_id IS NULL
        """, (match['reserve_number'], match['charter_id'], match['receipt_id']))
    
    conn.commit()
    print(f"✅ Updated {len(all_matches):,} receipts")
    
    # Final verification
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN reserve_number IS NOT NULL THEN 1 ELSE 0 END) as has_reserve,
            SUM(revenue) as total_revenue,
            SUM(CASE WHEN reserve_number IS NOT NULL THEN revenue ELSE 0 END) as linked_revenue
        FROM receipts
        WHERE revenue > 0
    """)
    r = cur.fetchone()
    print(f"\nFinal state:")
    print(f"  Total revenue receipts: {r[0]:,} (${r[2]:,.2f})")
    print(f"  Linked to charters: {r[1]:,} ({r[1]/r[0]*100:.1f}%)")
    print(f"  Linked revenue: ${r[3]:,.2f} ({r[3]/r[2]*100:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

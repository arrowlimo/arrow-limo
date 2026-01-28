#!/usr/bin/env python3
"""
Match receipts to banking transactions using multi-stage matching:
1. Exact amount match
2. If multiple: filter by date ±2 days
3. If still multiple: fuzzy match vendor name
4. Report results with confidence scores
"""

import os
import sys
import psycopg2
from datetime import timedelta
from difflib import SequenceMatcher
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def fuzzy_match_vendor(vendor1, vendor2):
    """Calculate similarity ratio between two vendor names."""
    if not vendor1 or not vendor2:
        return 0.0
    
    # Normalize: lowercase, strip whitespace
    v1 = vendor1.lower().strip()
    v2 = vendor2.lower().strip()
    
    # Direct substring match
    if v1 in v2 or v2 in v1:
        return 0.9
    
    # SequenceMatcher ratio
    return SequenceMatcher(None, v1, v2).ratio()

def match_receipt_to_banking(receipt, banking_candidates, date_tolerance=2):
    """
    Match a receipt to banking transactions using multi-stage logic.
    
    Returns: (matched_banking_id, confidence_level, match_reason)
    """
    receipt_id, receipt_date, receipt_vendor, receipt_amount = receipt
    
    if not banking_candidates:
        return None, 0.0, "No candidates"
    
    # Stage 1: Exact amount match
    exact_matches = [b for b in banking_candidates if b[3] == receipt_amount]
    
    if len(exact_matches) == 0:
        return None, 0.0, "No amount match"
    
    if len(exact_matches) == 1:
        return exact_matches[0][0], 1.0, "Exact amount (unique)"
    
    # Stage 2: Filter by date ±2 days
    date_filtered = []
    for banking in exact_matches:
        banking_id, banking_date, banking_desc, banking_amount = banking
        
        if banking_date and receipt_date:
            date_diff = abs((banking_date - receipt_date).days)
            if date_diff <= date_tolerance:
                date_filtered.append((banking, date_diff))
    
    if len(date_filtered) == 0:
        # No date matches within tolerance - report closest
        closest = min(exact_matches, 
                     key=lambda b: abs((b[1] - receipt_date).days) if b[1] and receipt_date else 999)
        days_off = abs((closest[1] - receipt_date).days) if closest[1] and receipt_date else 999
        return closest[0], 0.5, f"Amount match but date off by {days_off} days"
    
    if len(date_filtered) == 1:
        banking, days_diff = date_filtered[0]
        return banking[0], 0.95, f"Amount + date (±{days_diff} days)"
    
    # Stage 3: Fuzzy match vendor names
    best_match = None
    best_score = 0.0
    
    for banking, days_diff in date_filtered:
        banking_id, banking_date, banking_desc, banking_amount = banking
        
        # Calculate vendor similarity
        similarity = fuzzy_match_vendor(receipt_vendor, banking_desc)
        
        # Combined score: 70% vendor similarity, 30% date proximity
        date_score = 1.0 - (days_diff / date_tolerance)
        combined_score = (similarity * 0.7) + (date_score * 0.3)
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = (banking_id, banking_desc, similarity)
    
    if best_match and best_score >= 0.6:
        banking_id, banking_desc, vendor_sim = best_match
        return banking_id, best_score, f"Amount + date + vendor ({vendor_sim:.1%} similar)"
    
    # Multiple matches, couldn't disambiguate
    return None, 0.3, f"Multiple matches ({len(date_filtered)}), manual review needed"

def main():
    parser = argparse.ArgumentParser(description='Match receipts to banking transactions')
    parser.add_argument('--write', action='store_true', help='Write matches to database')
    parser.add_argument('--year', type=int, help='Limit to specific year (default: all years)')
    parser.add_argument('--min-confidence', type=float, default=0.8, 
                       help='Minimum confidence to auto-match (default: 0.8)')
    args = parser.parse_args()
    
    print("=" * 100)
    print("RECEIPTS TO BANKING MATCHING")
    print("=" * 100)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print(f"Minimum confidence: {args.min_confidence}")
    if args.year:
        print(f"Year filter: {args.year}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Step 1: Get unmatched receipts
    print("\n[1] Loading unmatched receipts...")
    
    year_filter = f"AND EXTRACT(YEAR FROM receipt_date) = {args.year}" if args.year else ""
    
    cur.execute(f"""
        SELECT 
            id,
            receipt_date,
            vendor_name,
            gross_amount
        FROM receipts
        WHERE mapped_bank_account_id IS NULL
          AND receipt_date IS NOT NULL
          AND gross_amount > 0
          {year_filter}
        ORDER BY receipt_date, id
    """)
    
    receipts = cur.fetchall()
    print(f"    Found {len(receipts)} unmatched receipts")
    
    if len(receipts) == 0:
        print("\n✓ No unmatched receipts to process")
        cur.close()
        conn.close()
        return
    
    # Step 2: Get potential banking matches (unlinked debits)
    print("\n[2] Loading banking transactions...")
    
    cur.execute(f"""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount
        FROM banking_transactions bt
        WHERE bt.debit_amount > 0
          AND NOT EXISTS (
              SELECT 1 FROM receipts r 
              WHERE r.mapped_bank_account_id = bt.transaction_id
          )
          {year_filter.replace('receipt_date', 'transaction_date')}
        ORDER BY bt.transaction_date
    """)
    
    banking_transactions = cur.fetchall()
    print(f"    Found {len(banking_transactions)} unlinked banking debits")
    
    # Step 3: Build amount index for quick lookup
    print("\n[3] Building amount index...")
    
    amount_index = {}
    for banking in banking_transactions:
        amount = banking[3]
        if amount not in amount_index:
            amount_index[amount] = []
        amount_index[amount].append(banking)
    
    print(f"    Indexed {len(amount_index)} unique amounts")
    
    # Step 4: Match each receipt
    print("\n[4] Matching receipts to banking...")
    
    matches = []
    no_match = []
    low_confidence = []
    
    for receipt in receipts:
        receipt_id, receipt_date, receipt_vendor, receipt_amount = receipt
        
        # Get banking candidates with exact amount
        candidates = amount_index.get(receipt_amount, [])
        
        # Attempt to match
        banking_id, confidence, reason = match_receipt_to_banking(
            receipt, candidates, date_tolerance=2
        )
        
        if banking_id and confidence >= args.min_confidence:
            matches.append((receipt_id, banking_id, confidence, reason))
        elif banking_id:
            low_confidence.append((receipt_id, banking_id, confidence, reason, 
                                  receipt_date, receipt_vendor, receipt_amount))
        else:
            no_match.append((receipt_id, receipt_date, receipt_vendor, receipt_amount, reason))
    
    # Step 5: Report results
    print("\n" + "=" * 100)
    print("MATCHING RESULTS")
    print("=" * 100)
    
    print(f"\n✓ High confidence matches: {len(matches)} (≥{args.min_confidence} confidence)")
    print(f"[WARN]  Low confidence matches: {len(low_confidence)} (<{args.min_confidence} confidence)")
    print(f"[FAIL] No matches found: {len(no_match)}")
    
    # Show sample high confidence matches
    if matches:
        print(f"\nSample high confidence matches (first 10):")
        for receipt_id, banking_id, conf, reason in matches[:10]:
            print(f"  Receipt {receipt_id} → Banking {banking_id} ({conf:.1%} - {reason})")
    
    # Show low confidence matches for review
    if low_confidence:
        print(f"\n[WARN]  Low confidence matches requiring review:")
        for receipt_id, banking_id, conf, reason, date, vendor, amount in low_confidence[:20]:
            print(f"  Receipt {receipt_id} → Banking {banking_id}")
            print(f"    {date} | {vendor} | ${amount:.2f}")
            print(f"    Confidence: {conf:.1%} - {reason}")
            print()
    
    # Show some no-match examples
    if no_match:
        print(f"\n[FAIL] No matches found (first 10):")
        for receipt_id, date, vendor, amount, reason in no_match[:10]:
            print(f"  Receipt {receipt_id}: {date} | {vendor} | ${amount:.2f}")
            print(f"    Reason: {reason}")
    
    # Step 6: Write matches if requested
    if args.write and matches:
        print("\n" + "=" * 100)
        print(f"[6] Writing {len(matches)} high confidence matches to database...")
        
        for receipt_id, banking_id, conf, reason in matches:
            cur.execute("""
                UPDATE receipts 
                SET mapped_bank_account_id = %s
                WHERE id = %s
            """, (banking_id, receipt_id))
        
        conn.commit()
        print(f"    ✓ Updated {len(matches)} receipts")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE mapped_bank_account_id IS NOT NULL
        """)
        total_linked = cur.fetchone()[0]
        print(f"    Total receipts now linked: {total_linked}")
    
    elif args.write:
        print("\n[WARN]  No high confidence matches to write")
    
    else:
        print("\n💡 Run with --write to save high confidence matches to database")
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Processed: {len(receipts)} unmatched receipts")
    print(f"High confidence matches: {len(matches)} ({len(matches)/len(receipts)*100:.1f}%)")
    print(f"Low confidence matches: {len(low_confidence)} ({len(low_confidence)/len(receipts)*100:.1f}%)")
    print(f"No matches: {len(no_match)} ({len(no_match)/len(receipts)*100:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Smart match Scotia 2012 banking transactions to existing receipts.
Strategy:
1. Match by exact amount first
2. If multiple matches, use vendor name similarity
3. If still ambiguous, use date proximity (within 7 days)
"""

import psycopg2
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import sys

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def vendor_similarity(vendor1, vendor2):
    """Calculate similarity between two vendor names (0.0 to 1.0)."""
    if not vendor1 or not vendor2:
        return 0.0
    v1 = vendor1.upper().strip()
    v2 = vendor2.upper().strip()
    return SequenceMatcher(None, v1, v2).ratio()

def extract_vendor_from_description(desc):
    """Extract likely vendor name from banking description."""
    if not desc:
        return None
    
    desc_upper = desc.upper()
    
    # Remove common prefixes
    prefixes = ['POS PURCHASE - ', 'DEBIT PURCHASE - ', 'POS ', 'PURCHASE ']
    for prefix in prefixes:
        if desc_upper.startswith(prefix):
            desc = desc[len(prefix):]
            break
    
    # Take first part before location/date info
    parts = desc.split()
    if len(parts) > 0:
        # Usually vendor is first 1-3 words
        return ' '.join(parts[:3]).strip()
    
    return desc.strip()

def main():
    write_mode = '--write' in sys.argv
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("SCOTIA 2012 SMART MATCHING - BANKING TO RECEIPTS")
    print("=" * 100)
    print(f"Mode: {'WRITE' if write_mode else 'DRY RUN'}")
    print()
    
    # Get all unmatched Scotia 2012 banking transactions
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND debit_amount > 0
            AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    unmatched_banking = cur.fetchall()
    
    print(f"Found {len(unmatched_banking)} unmatched banking transactions")
    print()
    
    # Get all receipts from 2012 that aren't already linked
    cur.execute("""
        SELECT 
            id,
            receipt_date,
            vendor_name,
            gross_amount,
            description
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND id NOT IN (
                SELECT receipt_id 
                FROM banking_transactions 
                WHERE receipt_id IS NOT NULL
            )
        ORDER BY receipt_date
    """)
    
    available_receipts = cur.fetchall()
    
    print(f"Found {len(available_receipts)} available receipts from 2012")
    print()
    
    # Build index by amount for fast lookup
    receipts_by_amount = {}
    for receipt_id, date, vendor, amount, desc in available_receipts:
        if amount not in receipts_by_amount:
            receipts_by_amount[amount] = []
        receipts_by_amount[amount].append({
            'id': receipt_id,
            'date': date,
            'vendor': vendor,
            'amount': amount,
            'description': desc
        })
    
    # Match transactions to receipts
    matches = []
    exact_matches = 0
    vendor_matches = 0
    date_matches = 0
    no_matches = 0
    
    for txn_id, txn_date, txn_desc, txn_amount in unmatched_banking:
        # Step 1: Find receipts with exact amount
        candidates = receipts_by_amount.get(txn_amount, [])
        
        if len(candidates) == 0:
            no_matches += 1
            continue
        
        if len(candidates) == 1:
            # Single match by amount - use it
            match = candidates[0]
            matches.append({
                'txn_id': txn_id,
                'txn_date': txn_date,
                'txn_desc': txn_desc,
                'txn_amount': txn_amount,
                'receipt_id': match['id'],
                'receipt_date': match['date'],
                'receipt_vendor': match['vendor'],
                'match_type': 'exact_amount',
                'confidence': 1.0
            })
            exact_matches += 1
            continue
        
        # Step 2: Multiple matches - try vendor similarity
        txn_vendor = extract_vendor_from_description(txn_desc)
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            # Calculate vendor similarity
            vendor_score = vendor_similarity(txn_vendor, candidate['vendor'])
            
            # Calculate date proximity (within 7 days = 1.0, further away = lower)
            if txn_date and candidate['date']:
                date_diff = abs((txn_date - candidate['date']).days)
                date_score = max(0, 1.0 - (date_diff / 7.0))
            else:
                date_score = 0.5
            
            # Combined score (vendor weighted more heavily)
            combined_score = (vendor_score * 0.7) + (date_score * 0.3)
            
            if combined_score > best_score:
                best_score = combined_score
                best_match = candidate
        
        if best_match and best_score > 0.5:  # Confidence threshold
            if best_score > 0.8:
                match_type = 'vendor_strong'
                vendor_matches += 1
            else:
                match_type = 'vendor_date'
                date_matches += 1
            
            matches.append({
                'txn_id': txn_id,
                'txn_date': txn_date,
                'txn_desc': txn_desc,
                'txn_amount': txn_amount,
                'receipt_id': best_match['id'],
                'receipt_date': best_match['date'],
                'receipt_vendor': best_match['vendor'],
                'match_type': match_type,
                'confidence': best_score
            })
        else:
            no_matches += 1
    
    print("=" * 100)
    print("MATCHING RESULTS")
    print("=" * 100)
    print(f"Exact amount matches: {exact_matches}")
    print(f"Vendor similarity matches: {vendor_matches}")
    print(f"Date proximity matches: {date_matches}")
    print(f"No matches found: {no_matches}")
    print(f"Total matches: {len(matches)}")
    print()
    
    if matches:
        print("=" * 100)
        print("SAMPLE MATCHES (first 10)")
        print("=" * 100)
        
        for i, match in enumerate(matches[:10], 1):
            print(f"\n{i}. {match['match_type'].upper()} (confidence: {match['confidence']:.2f})")
            print(f"   Banking: {match['txn_date']} | ${match['txn_amount']:,.2f} | {match['txn_desc'][:60]}")
            print(f"   Receipt: {match['receipt_date']} | ${match['txn_amount']:,.2f} | {match['receipt_vendor']}")
        
        if len(matches) > 10:
            print(f"\n   ... and {len(matches) - 10} more matches")
    
    if write_mode:
        print("\n" + "=" * 100)
        print("APPLYING MATCHES TO DATABASE")
        print("=" * 100)
        
        for match in matches:
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (match['receipt_id'], match['txn_id']))
        
        conn.commit()
        print(f"Updated {len(matches)} banking transactions with receipt links")
        
        # Verify
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched_debits
            FROM banking_transactions
            WHERE account_number = '903990106011'
                AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        total, matched = cur.fetchone()
        match_rate = 100 * matched / total if total > 0 else 0
        
        print("\n" + "=" * 100)
        print("VERIFICATION")
        print("=" * 100)
        print(f"Scotia 2012 debits: {matched}/{total} matched ({match_rate:.1f}%)")
        print(f"Improvement: {matched - 43} additional matches (was 43, now {matched})")
    else:
        print("\n" + "=" * 100)
        print("DRY RUN - NO CHANGES MADE")
        print("Run with --write flag to apply matches")
        print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

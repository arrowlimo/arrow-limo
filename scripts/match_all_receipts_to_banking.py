#!/usr/bin/env python3
"""
Match all receipts to CIBC and Scotia banking transactions.
Uses multiple matching strategies: date+amount, vendor name, description matching.
"""

import psycopg2
import os
import re
from datetime import datetime, timedelta
import hashlib

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def normalize_vendor(vendor):
    """Normalize vendor name for matching."""
    if not vendor:
        return ""
    vendor = vendor.upper().strip()
    # Remove common suffixes
    vendor = re.sub(r'\s+(LTD|INC|CORP|CO|LLC|CANADA|CDN)\.?$', '', vendor)
    # Remove special characters
    vendor = re.sub(r'[^\w\s]', '', vendor)
    # Collapse whitespace
    vendor = re.sub(r'\s+', ' ', vendor)
    return vendor.strip()

def extract_amount_from_description(description):
    """Extract dollar amounts from banking description."""
    amounts = re.findall(r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', description)
    if amounts:
        return float(amounts[0].replace(',', ''))
    return None

def match_receipt_to_banking(cur, receipt, banking_transactions):
    """
    Try to match a receipt to banking transactions using multiple strategies.
    Returns (transaction_id, match_type, confidence) or (None, None, 0)
    """
    receipt_id = receipt[0]
    receipt_date = receipt[1]
    vendor = receipt[2]
    amount = float(receipt[3])
    category = receipt[4]
    
    normalized_vendor = normalize_vendor(vendor)
    
    # Strategy 1: Exact date and amount match
    for bt in banking_transactions:
        bt_id, bt_date, bt_desc, bt_debit, bt_credit = bt
        bt_amount = bt_debit if bt_debit else bt_credit
        
        if bt_date == receipt_date and abs(float(bt_amount) - amount) < 0.01:
            # Check if vendor appears in description
            if normalized_vendor and normalized_vendor in normalize_vendor(bt_desc):
                return (bt_id, 'exact_date_amount_vendor', 100)
            return (bt_id, 'exact_date_amount', 95)
    
    # Strategy 2: Date within 3 days and exact amount with vendor match
    date_window_start = receipt_date - timedelta(days=3)
    date_window_end = receipt_date + timedelta(days=3)
    
    for bt in banking_transactions:
        bt_id, bt_date, bt_desc, bt_debit, bt_credit = bt
        bt_amount = bt_debit if bt_debit else bt_credit
        
        if date_window_start <= bt_date <= date_window_end:
            if abs(float(bt_amount) - amount) < 0.01:
                if normalized_vendor and len(normalized_vendor) >= 4:
                    if normalized_vendor in normalize_vendor(bt_desc):
                        return (bt_id, 'near_date_exact_amount_vendor', 90)
    
    # Strategy 3: Exact date with vendor match (amount may differ slightly due to GST)
    for bt in banking_transactions:
        bt_id, bt_date, bt_desc, bt_debit, bt_credit = bt
        bt_amount = bt_debit if bt_debit else bt_credit
        
        if bt_date == receipt_date and normalized_vendor and len(normalized_vendor) >= 4:
            if normalized_vendor in normalize_vendor(bt_desc):
                # Allow 15% variance for GST differences
                amount_diff = abs(float(bt_amount) - amount)
                if amount_diff / amount < 0.15:
                    return (bt_id, 'exact_date_vendor_near_amount', 85)
    
    # Strategy 4: Known vendor patterns (gas stations, banks, etc.)
    vendor_patterns = {
        'CENTEX': ['CENTEX', 'CENTEX PETROLEUM'],
        'FAS GAS': ['FAS GAS', 'FASGAS'],
        'SHELL': ['SHELL', 'SHELL CANADA'],
        'ESSO': ['ESSO'],
        'PETRO': ['PETRO', 'PETRO CANADA', 'PETRO-CANADA'],
        'HUSKY': ['HUSKY'],
        'CO-OP': ['CO-OP', 'COOP'],
        'CANADIAN TIRE': ['CANADIAN TIRE', 'CDN TIRE'],
        'STAPLES': ['STAPLES'],
        'TELUS': ['TELUS'],
        'HEFFNER': ['HEFFNER'],
    }
    
    for pattern_key, patterns in vendor_patterns.items():
        if any(p in normalized_vendor for p in patterns):
            for bt in banking_transactions:
                bt_id, bt_date, bt_desc, bt_debit, bt_credit = bt
                
                if date_window_start <= bt_date <= date_window_end:
                    if any(p in normalize_vendor(bt_desc) for p in patterns):
                        bt_amount = bt_debit if bt_debit else bt_credit
                        amount_diff = abs(float(bt_amount) - amount)
                        if amount_diff / amount < 0.20:  # 20% tolerance
                            return (bt_id, 'vendor_pattern_match', 80)
    
    return (None, None, 0)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Match receipts to banking transactions')
    parser.add_argument('--write', action='store_true', help='Write matches to database')
    parser.add_argument('--min-confidence', type=int, default=80, help='Minimum confidence score (default: 80)')
    parser.add_argument('--start-date', default=None, help='Optional start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default=None, help='Optional end date (YYYY-MM-DD)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("RECEIPT TO BANKING MATCHING ENGINE")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print(f"Minimum confidence: {args.min_confidence}%")
    
    # Get all business receipts that are not yet matched
    print("\n1. Loading unmatched business receipts...")
    receipts_where = "r.business_personal = 'Business' AND NOT EXISTS (SELECT 1 FROM banking_receipt_matching_ledger bm WHERE bm.receipt_id = r.receipt_id)"
    params = []
    if args.start_date:
        receipts_where += " AND r.receipt_date >= %s"
        params.append(args.start_date)
    if args.end_date:
        receipts_where += " AND r.receipt_date <= %s"
        params.append(args.end_date)

    receipts_sql = f"""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.category
        FROM receipts r
        WHERE {receipts_where}
        ORDER BY r.receipt_date, r.receipt_id
    """
    cur.execute(receipts_sql, params)
    
    receipts = cur.fetchall()
    print(f"   Found {len(receipts)} unmatched business receipts")
    
    # Get all banking transactions from CIBC and Scotia (debits only - expenses)
    print("\n2. Loading banking transactions (CIBC + Scotia)...")
    banking_where = "account_number IN ('0228362', '903990106011', '3648117') AND (debit_amount IS NOT NULL OR credit_amount IS NOT NULL)"
    banking_params = []
    if args.start_date:
        banking_where += " AND transaction_date >= %s"
        banking_params.append(args.start_date)
    if args.end_date:
        banking_where += " AND transaction_date <= %s"
        banking_params.append(args.end_date)

    banking_sql = f"""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE {banking_where}
        ORDER BY transaction_date, transaction_id
    """
    cur.execute(banking_sql, banking_params)
    
    banking_transactions = cur.fetchall()
    print(f"   Found {len(banking_transactions)} banking transactions")
    
    # Match receipts to banking
    print("\n3. Matching receipts to banking transactions...")
    
    matches = []
    match_stats = {
        'exact_date_amount_vendor': 0,
        'exact_date_amount': 0,
        'near_date_exact_amount_vendor': 0,
        'exact_date_vendor_near_amount': 0,
        'vendor_pattern_match': 0,
    }
    
    for i, receipt in enumerate(receipts):
        if (i + 1) % 100 == 0:
            print(f"   Processing {i+1}/{len(receipts)}...")
        
        bt_id, match_type, confidence = match_receipt_to_banking(cur, receipt, banking_transactions)
        
        if bt_id and confidence >= args.min_confidence:
            matches.append({
                'receipt_id': receipt[0],
                'banking_transaction_id': bt_id,
                'match_type': match_type,
                'confidence': confidence,
                'receipt_date': receipt[1],
                'vendor': receipt[2],
                'amount': receipt[3]
            })
            match_stats[match_type] = match_stats.get(match_type, 0) + 1
    
    print(f"\n   Found {len(matches)} potential matches")
    
    # Display match statistics
    print("\n4. Match quality breakdown:")
    for match_type, count in sorted(match_stats.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"   {match_type:35} {count:5} matches")
    
    # Sample matches
    if matches:
        print("\n5. Sample matches (first 20):")
        print(f"   {'Receipt ID':>10} {'Date':>12} {'Vendor':>30} {'Amount':>12} {'Type':>25} {'Conf':>5}")
        print(f"   {'-'*10} {'-'*12} {'-'*30} {'-'*12} {'-'*25} {'-'*5}")
        
        for match in matches[:20]:
            vendor_display = (match['vendor'] or 'Unknown')[:30]
            print(f"   {match['receipt_id']:10} {str(match['receipt_date']):12} {vendor_display:30} "
                  f"${match['amount']:10.2f} {match['match_type']:25} {match['confidence']:4}%")
    
    # Write matches to database
    if args.write and matches:
        print(f"\n6. Writing {len(matches)} matches to banking_receipt_matching_ledger...")
        
        created = 0
        skipped = 0
        
        for match in matches:
            try:
                # Check if link already exists
                cur.execute("""
                    SELECT id FROM banking_receipt_matching_ledger
                    WHERE receipt_id = %s AND banking_transaction_id = %s
                """, (match['receipt_id'], match['banking_transaction_id']))
                
                if cur.fetchone():
                    skipped += 1
                    continue
                
                # Create link
                cur.execute("""
                    INSERT INTO banking_receipt_matching_ledger 
                    (receipt_id, banking_transaction_id, match_confidence, match_type, match_date, match_status)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 'matched')
                """, (match['receipt_id'], match['banking_transaction_id'], 
                      str(match['confidence']), match['match_type']))
                
                created += 1
                
            except Exception as e:
                print(f"   Error linking receipt {match['receipt_id']}: {e}")
        
        conn.commit()
        print(f"   Created {created} new links, skipped {skipped} existing")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total unmatched receipts: {len(receipts)}")
    print(f"Potential matches found: {len(matches)} ({len(matches)/len(receipts)*100:.1f}% if all matched)")
    
    if args.write:
        print(f"\nMatches written to database: {created}")
        print(f"Links already existed: {skipped}")
    else:
        print("\nDRY RUN - No changes made")
        print("Run with --write to apply matches")
    
    print("\n" + "="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

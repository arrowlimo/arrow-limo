#!/usr/bin/env python3
"""
Clean vendor names for account 903990106011 and match to receipts.
Normalizes descriptions and creates banking_receipt_matching_ledger entries.
"""

import psycopg2
import os
import re
from datetime import timedelta

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def normalize_vendor(description):
    """Normalize vendor name from banking description."""
    if not description:
        return ""
    
    vendor = description.upper().strip()
    
    # Remove common suffixes
    vendor = re.sub(r'\s+(CORP|INC|CANADA|CDN|CO|LLC|LTD|INC\.?|CORP\.?)\.?$', '', vendor)
    
    # Remove special characters except spaces and basic punctuation
    vendor = re.sub(r'[^\w\s\-\&]', '', vendor)
    
    # Collapse multiple spaces
    vendor = re.sub(r'\s+', ' ', vendor).strip()
    
    # Common vendor standardizations
    replacements = {
        r'^CENTEX': 'CENTEX',
        r'^FAS\s*GAS': 'FAS GAS',
        r'^SHELL': 'SHELL',
        r'^ESSO': 'ESSO',
        r'^PETRO\s*CAN': 'PETRO-CAN',
        r'^CO\s*OP': 'CO-OP',
        r'^HEFFNER': 'HEFFNER',
        r'^CANADIAN\s*TIRE': 'CANADIAN TIRE',
        r'^STAPLES': 'STAPLES',
        r'^TELUS': 'TELUS',
        r'^LIQUOR\s*BARN': 'LIQUOR BARN',
        r'^REXALL': 'REXALL',
        r'^SHOPPERS': 'SHOPPERS DRUG MART',
        r'^RUN\s*N\s*ON\s*EMPTY': "RUN'N ON EMPTY",
        r'^PARKLAND': 'PARKLAND',
        r'^ACE\s*TRUCK': 'ACE TRUCK RENTALS',
    }
    
    for pattern, replacement in replacements.items():
        if re.match(pattern, vendor):
            vendor = replacement
            break
    
    return vendor

def match_receipt_to_banking(receipt, banking_rows):
    """Match a receipt to banking transactions."""
    receipt_id, receipt_date, vendor, gross_amount = receipt
    amount = float(gross_amount)
    
    # Strategy 1: Exact date and amount with vendor match
    for bt_id, bt_date, bt_desc, bt_debit, bt_credit in banking_rows:
        bt_amount = float(bt_debit) if bt_debit else float(bt_credit) if bt_credit else 0
        
        if bt_date == receipt_date and abs(bt_amount - amount) < 0.01:
            normalized_bank_vendor = normalize_vendor(bt_desc)
            normalized_receipt_vendor = normalize_vendor(vendor)
            
            if normalized_receipt_vendor and normalized_receipt_vendor in normalized_bank_vendor:
                return (bt_id, 'exact_date_amount_vendor', '100')
            if normalized_receipt_vendor and normalized_receipt_vendor == normalized_bank_vendor:
                return (bt_id, 'exact_date_amount_vendor', '100')
            return (bt_id, 'exact_date_amount', '95')
    
    # Strategy 2: Date within 3 days and exact amount with vendor match
    date_window_start = receipt_date - timedelta(days=3)
    date_window_end = receipt_date + timedelta(days=3)
    
    for bt_id, bt_date, bt_desc, bt_debit, bt_credit in banking_rows:
        bt_amount = float(bt_debit) if bt_debit else float(bt_credit) if bt_credit else 0
        
        if date_window_start <= bt_date <= date_window_end and abs(bt_amount - amount) < 0.01:
            normalized_bank_vendor = normalize_vendor(bt_desc)
            normalized_receipt_vendor = normalize_vendor(vendor)
            
            if normalized_receipt_vendor and len(normalized_receipt_vendor) >= 4:
                if normalized_receipt_vendor in normalized_bank_vendor:
                    return (bt_id, 'near_date_exact_amount_vendor', '90')
    
    # Strategy 3: Exact date and vendor (amount may differ due to GST)
    for bt_id, bt_date, bt_desc, bt_debit, bt_credit in banking_rows:
        bt_amount = float(bt_debit) if bt_debit else float(bt_credit) if bt_credit else 0
        
        if bt_date == receipt_date:
            normalized_bank_vendor = normalize_vendor(bt_desc)
            normalized_receipt_vendor = normalize_vendor(vendor)
            
            if normalized_receipt_vendor and len(normalized_receipt_vendor) >= 4:
                if normalized_receipt_vendor in normalized_bank_vendor:
                    amount_diff = abs(bt_amount - amount)
                    if amount / 100 < amount_diff < amount * 0.15:  # GST tolerance
                        return (bt_id, 'exact_date_vendor_near_amount', '85')
    
    return (None, None, None)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Clean and match Scotia 903990106011')
    parser.add_argument('--write', action='store_true', help='Write matches to database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    acct = '903990106011'
    
    print("\n" + "="*80)
    print(f"SCOTIA ACCOUNT {acct} - VENDOR CLEANUP & RECEIPT MATCHING")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}\n")
    
    # Get all banking transactions for this account
    print("1. Loading banking transactions...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
        ORDER BY transaction_date, transaction_id
    """, (acct,))
    banking_rows = cur.fetchall()
    print(f"   Loaded {len(banking_rows)} banking transactions")
    
    # Get unmatched business receipts
    print("\n2. Loading unmatched business receipts...")
    cur.execute("""
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount
        FROM receipts r
        WHERE r.business_personal = 'Business'
        AND r.mapped_bank_account_id = 2  -- Scotia account
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.receipt_id = r.receipt_id
        )
        ORDER BY r.receipt_date, r.receipt_id
    """)
    receipts = cur.fetchall()
    print(f"   Found {len(receipts)} unmatched business receipts for Scotia")
    
    # Match receipts to banking
    print("\n3. Matching receipts to banking transactions...")
    matches = []
    match_stats = {}
    
    for i, receipt in enumerate(receipts):
        if (i + 1) % 100 == 0:
            print(f"   Processing {i+1}/{len(receipts)}...")
        
        bt_id, match_type, confidence = match_receipt_to_banking(receipt, banking_rows)
        
        if bt_id:
            matches.append({
                'receipt_id': receipt[0],
                'banking_transaction_id': bt_id,
                'match_type': match_type,
                'confidence': confidence,
            })
            match_stats[match_type] = match_stats.get(match_type, 0) + 1
    
    print(f"\n   Found {len(matches)} matches")
    print("   Match breakdown:")
    for match_type in sorted(match_stats.keys()):
        print(f"     {match_type}: {match_stats[match_type]}")
    
    # Create/update banking_receipt_matching_ledger entries
    if args.write and matches:
        print("\n4. Writing matches to banking_receipt_matching_ledger...")
        inserted = 0
        for match in matches:
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger
                (banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes, created_by)
                VALUES (%s, %s, CURRENT_DATE, %s, 'matched', %s, 'Auto-matched from Scotia 903990106011 cleanup', 'system')
                ON CONFLICT DO NOTHING
            """, (
                match['banking_transaction_id'],
                match['receipt_id'],
                match['match_type'],
                match['confidence']
            ))
            inserted += cur.rowcount
        
        conn.commit()
        print(f"   Inserted {inserted} matching ledger entries")
    elif matches:
        print(f"\n4. (DRY RUN) Would insert {len(matches)} matching ledger entries")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("Done.")
    print("="*80)

if __name__ == '__main__':
    main()

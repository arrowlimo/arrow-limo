#!/usr/bin/env python3
"""
Apply smart matching to CIBC account 1010 (2013).

This account has 974 unmatched debits - apply the same proven techniques
used for Scotia 2012: exact amount matching, fuzzy vendor matching, 
date proximity, and description pattern analysis.
"""

import psycopg2
import os
import argparse
from datetime import timedelta
from decimal import Decimal
import hashlib

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def normalize_vendor(vendor):
    """Normalize vendor name for fuzzy matching."""
    if not vendor:
        return ""
    v = str(vendor).upper().strip()
    # Remove common suffixes
    for suffix in [' LTD', ' INC', ' CORP', ' CO', ' LLC']:
        if v.endswith(suffix):
            v = v[:-len(suffix)].strip()
    return v

def match_receipt_to_banking(receipt, banking_transactions):
    """
    Match a receipt to banking transactions using multi-stage logic.
    
    Returns: (transaction_id, confidence_score, match_reason) or (None, 0, None)
    """
    receipt_date = receipt[2]
    receipt_amount = Decimal(str(receipt[3]))
    receipt_vendor = normalize_vendor(receipt[4])
    
    best_match = None
    best_score = 0
    best_reason = None
    
    for banking in banking_transactions:
        trans_id, trans_date, trans_amount, trans_desc = banking
        trans_amount = Decimal(str(trans_amount))
        
        # Stage 1: Exact amount + same date
        if abs(receipt_amount - trans_amount) < Decimal('0.01') and receipt_date == trans_date:
            vendor_match = receipt_vendor and receipt_vendor in normalize_vendor(trans_desc)
            if vendor_match:
                return (trans_id, 100, "Exact amount + date + vendor")
            else:
                if best_score < 90:
                    best_match = trans_id
                    best_score = 90
                    best_reason = "Exact amount + date"
        
        # Stage 2: Exact amount + within 3 days
        elif abs(receipt_amount - trans_amount) < Decimal('0.01'):
            days_diff = abs((receipt_date - trans_date).days)
            if days_diff <= 3:
                vendor_match = receipt_vendor and receipt_vendor in normalize_vendor(trans_desc)
                score = 85 if vendor_match else 75
                score -= (days_diff * 5)  # Penalize for date difference
                
                if score > best_score:
                    best_match = trans_id
                    best_score = score
                    best_reason = f"Exact amount + {days_diff}d diff" + (" + vendor" if vendor_match else "")
        
        # Stage 3: Amount within $5 + same date + vendor match
        elif abs(receipt_amount - trans_amount) < Decimal('5.00') and receipt_date == trans_date:
            vendor_match = receipt_vendor and receipt_vendor in normalize_vendor(trans_desc)
            if vendor_match and best_score < 70:
                best_match = trans_id
                best_score = 70
                best_reason = f"Close amount (${abs(receipt_amount - trans_amount):.2f} diff) + date + vendor"
    
    return (best_match, best_score, best_reason) if best_match else (None, 0, None)

def smart_match_cibc_1010(dry_run=True):
    """Apply smart matching to CIBC account 1010."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print(" " * 25 + "CIBC ACCOUNT 1010 SMART MATCHING (2013)")
    print("=" * 100)
    print()
    
    if dry_run:
        print("DRY RUN MODE - No database changes will be made")
        print()
    
    # Get unmatched receipts from 2013
    print("[1] Loading receipts from 2013...")
    cur.execute("""
        SELECT 
            id,
            vendor_name,
            receipt_date,
            gross_amount,
            vendor_name,
            description,
            category
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2013
          AND (source_reference IS NULL OR source_reference NOT LIKE 'banking_%')
        ORDER BY receipt_date, gross_amount
    """)
    
    receipts = cur.fetchall()
    print(f"    Found {len(receipts)} unmatched receipts")
    print()
    
    # Get unmatched banking transactions from account 1010
    print("[2] Loading banking transactions from account 1010...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            debit_amount,
            description
        FROM banking_transactions
        WHERE account_number = '1010'
          AND EXTRACT(YEAR FROM transaction_date) = 2013
          AND debit_amount > 0
          AND receipt_id IS NULL
        ORDER BY transaction_date, debit_amount
    """)
    
    banking_transactions = cur.fetchall()
    print(f"    Found {len(banking_transactions)} unlinked banking debits")
    print()
    
    # Match receipts to banking
    print("[3] Matching receipts to banking transactions...")
    print()
    
    matches = []
    confidence_buckets = {
        'high': [],      # 85-100
        'medium': [],    # 70-84
        'low': []        # < 70
    }
    
    for receipt in receipts:
        match_id, confidence, reason = match_receipt_to_banking(receipt, banking_transactions)
        
        if match_id:
            matches.append((receipt, match_id, confidence, reason))
            
            if confidence >= 85:
                confidence_buckets['high'].append((receipt, match_id, confidence, reason))
            elif confidence >= 70:
                confidence_buckets['medium'].append((receipt, match_id, confidence, reason))
            else:
                confidence_buckets['low'].append((receipt, match_id, confidence, reason))
    
    print(f"    Total matches found: {len(matches)}")
    print(f"      High confidence (85-100): {len(confidence_buckets['high'])}")
    print(f"      Medium confidence (70-84): {len(confidence_buckets['medium'])}")
    print(f"      Low confidence (<70): {len(confidence_buckets['low'])}")
    print()
    
    # Show sample matches
    if confidence_buckets['high']:
        print("Sample High Confidence Matches (showing first 5):")
        print(f"{'Date':<12} {'Receipt Amt':>12} {'Bank Amt':>12} {'Vendor':<30} {'Reason':<40}")
        print("-" * 110)
        
        for receipt, trans_id, confidence, reason in confidence_buckets['high'][:5]:
            rec_id, vendor, date, amount, _, _, _ = receipt
            
            # Get banking transaction details
            cur.execute("SELECT transaction_date, debit_amount FROM banking_transactions WHERE transaction_id = %s", (trans_id,))
            bank_date, bank_amount = cur.fetchone()
            
            print(f"{date} ${amount:>11,.2f} ${bank_amount:>11,.2f} {vendor[:30]:<30} {reason[:40]}")
        print()
    
    # Apply matches if not dry run
    if not dry_run:
        print(f"[4] Applying {len(matches)} matches to database...")
        
        for receipt, trans_id, confidence, reason in matches:
            rec_id = receipt[0]
            
            # Update receipt with source_reference
            cur.execute("""
                UPDATE receipts
                SET source_reference = %s,
                    notes = COALESCE(notes, '') || %s
                WHERE id = %s
            """, (
                f"banking_{trans_id}",
                f"\nMatched via smart matching: {reason} (confidence: {confidence})",
                rec_id
            ))
            
            # Update banking transaction with receipt_id
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (rec_id, trans_id))
        
        conn.commit()
        print(f"    Applied {len(matches)} matches successfully")
        print()
        
        # Verify
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE account_number = '1010'
              AND debit_amount > 0
              AND receipt_id IS NOT NULL
        """)
        matched_count = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE account_number = '1010'
              AND debit_amount > 0
        """)
        total_count = cur.fetchone()[0]
        
        print(f"Verification: {matched_count}/{total_count} debits now matched ({matched_count/total_count*100:.1f}%)")
    else:
        print("[4] DRY RUN - Add --write flag to apply matches")
    
    print()
    print("=" * 100)
    
    cur.close()
    conn.close()
    
    return len(matches)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Smart match CIBC 1010 receipts to banking')
    parser.add_argument('--write', action='store_true', help='Apply matches (default is dry-run)')
    args = parser.parse_args()
    
    matches = smart_match_cibc_1010(dry_run=not args.write)
    
    if not args.write and matches > 0:
        print(f"\nFound {matches} potential matches. Run with --write to apply.")

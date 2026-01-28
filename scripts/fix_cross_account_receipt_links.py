#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix cross-account receipt-banking links.

Issue: 917 receipts have mapped_bank_account_id that doesn't match the actual
banking transaction account they're linked to via banking_receipt_matching_ledger.

Solution: Update receipt.mapped_bank_account_id to match the banking transaction's
actual account:
  - If banking txn is 0228362 -> receipt should be mapped_bank_account_id = 1
  - If banking txn is 903990106011 -> receipt should be mapped_bank_account_id = 2
"""
import os
import sys
import psycopg2
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    dry_run = '--write' not in sys.argv
    conn = get_conn()
    cur = conn.cursor()

    print("Fixing cross-account receipt-banking links")
    print("=" * 70)
    
    # Find CIBC transactions linked to Scotia receipts
    cur.execute("""
        SELECT DISTINCT r.receipt_id, r.vendor_name, r.mapped_bank_account_id, bt.account_number
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id = 2
    """)
    cibc_wrong = cur.fetchall()
    
    # Find Scotia transactions linked to CIBC receipts
    cur.execute("""
        SELECT DISTINCT r.receipt_id, r.vendor_name, r.mapped_bank_account_id, bt.account_number
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id = 1
    """)
    scotia_wrong = cur.fetchall()
    
    print(f"\nFound {len(cibc_wrong)} receipts marked as Scotia but linked to CIBC")
    print(f"Found {len(scotia_wrong)} receipts marked as CIBC but linked to Scotia")
    print(f"Total receipts to correct: {len(cibc_wrong) + len(scotia_wrong)}")
    
    if dry_run:
        print("\n[DRY RUN] Would update:")
        if cibc_wrong:
            print(f"\n  {len(cibc_wrong)} receipts: mapped_bank_account_id 2 -> 1 (Scotia -> CIBC)")
            for i, row in enumerate(cibc_wrong[:5]):
                print(f"    Receipt {row[0]} ({row[1][:40]})")
            if len(cibc_wrong) > 5:
                print(f"    ... and {len(cibc_wrong) - 5} more")
        
        if scotia_wrong:
            print(f"\n  {len(scotia_wrong)} receipts: mapped_bank_account_id 1 -> 2 (CIBC -> Scotia)")
            for i, row in enumerate(scotia_wrong[:5]):
                print(f"    Receipt {row[0]} ({row[1][:40]})")
            if len(scotia_wrong) > 5:
                print(f"    ... and {len(scotia_wrong) - 5} more")
        
        print("\nRun with --write to apply changes.")
        cur.close()
        conn.close()
        return
    
    # Apply corrections
    print("\n[WRITE MODE] Applying corrections...")
    
    if cibc_wrong:
        receipt_ids = [r[0] for r in cibc_wrong]
        cur.execute("""
            UPDATE receipts
            SET mapped_bank_account_id = 1
            WHERE receipt_id = ANY(%s)
        """, (receipt_ids,))
        print(f"✓ Updated {cur.rowcount} receipts from Scotia -> CIBC")
    
    if scotia_wrong:
        receipt_ids = [r[0] for r in scotia_wrong]
        cur.execute("""
            UPDATE receipts
            SET mapped_bank_account_id = 2
            WHERE receipt_id = ANY(%s)
        """, (receipt_ids,))
        print(f"✓ Updated {cur.rowcount} receipts from CIBC -> Scotia")
    
    conn.commit()
    print("\n✓ All corrections applied successfully.")
    
    # Verify
    print("\nVerifying fix...")
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id = 2
    """)
    remaining_cibc = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id = 1
    """)
    remaining_scotia = cur.fetchone()[0]
    
    if remaining_cibc == 0 and remaining_scotia == 0:
        print("✓ Verification passed: No cross-account links remain.")
    else:
        print(f"⚠ Warning: {remaining_cibc + remaining_scotia} cross-account links still exist.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

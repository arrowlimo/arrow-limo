#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix receipts with NULL mapped_bank_account_id by setting them to match
the banking transactions they're linked to.

For receipts linked to only ONE account: set to that account.
For receipts linked to BOTH accounts: set to the account with more links.
"""
import os
import sys
import psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    dry_run = '--write' not in sys.argv
    conn = get_conn()
    cur = conn.cursor()

    print("Fixing receipts with NULL or mismatched mapped_bank_account_id")
    print("=" * 70)
    
    # Strategy: For each receipt, determine dominant account and set mapped_id
    cur.execute("""
        WITH receipt_account_analysis AS (
            SELECT 
                r.receipt_id,
                r.vendor_name,
                r.mapped_bank_account_id as current_mapping,
                COUNT(CASE WHEN bt.account_number = '0228362' THEN 1 END) as cibc_links,
                COUNT(CASE WHEN bt.account_number = '903990106011' THEN 1 END) as scotia_links,
                CASE 
                    WHEN COUNT(CASE WHEN bt.account_number = '0228362' THEN 1 END) > 
                         COUNT(CASE WHEN bt.account_number = '903990106011' THEN 1 END) THEN 1
                    WHEN COUNT(CASE WHEN bt.account_number = '903990106011' THEN 1 END) > 
                         COUNT(CASE WHEN bt.account_number = '0228362' THEN 1 END) THEN 2
                    ELSE 1  -- tie-breaker: default to CIBC
                END as should_be_mapped
            FROM receipts r
            JOIN banking_receipt_matching_ledger bm ON bm.receipt_id = r.receipt_id
            JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
            WHERE bt.account_number IN ('0228362', '903990106011')
            GROUP BY r.receipt_id, r.vendor_name, r.mapped_bank_account_id
        )
        SELECT receipt_id, vendor_name, current_mapping, cibc_links, scotia_links, should_be_mapped
        FROM receipt_account_analysis
        WHERE current_mapping IS DISTINCT FROM should_be_mapped
        ORDER BY receipt_id
    """)
    
    to_fix = cur.fetchall()
    print(f"\nFound {len(to_fix)} receipts needing correction")
    
    # Group by correction type
    null_to_cibc = [r for r in to_fix if r[2] is None and r[5] == 1]
    null_to_scotia = [r for r in to_fix if r[2] is None and r[5] == 2]
    cibc_to_scotia = [r for r in to_fix if r[2] == 1 and r[5] == 2]
    scotia_to_cibc = [r for r in to_fix if r[2] == 2 and r[5] == 1]
    
    print(f"  NULL -> CIBC (1): {len(null_to_cibc)}")
    print(f"  NULL -> Scotia (2): {len(null_to_scotia)}")
    print(f"  CIBC (1) -> Scotia (2): {len(cibc_to_scotia)}")
    print(f"  Scotia (2) -> CIBC (1): {len(scotia_to_cibc)}")
    
    if dry_run:
        print("\n[DRY RUN] Sample corrections:")
        for r in to_fix[:10]:
            cur_map = r[2] if r[2] is not None else 'NULL'
            print(f"  Receipt {r[0]} '{r[1][:30]}' {cur_map} -> {r[5]} (CIBC:{r[3]} Scotia:{r[4]})")
        if len(to_fix) > 10:
            print(f"  ... and {len(to_fix) - 10} more")
        print("\nRun with --write to apply changes.")
        cur.close()
        conn.close()
        return
    
    # Apply corrections
    print("\n[WRITE MODE] Applying corrections...")
    
    for correction_type, receipts in [
        ("NULL -> CIBC", null_to_cibc),
        ("NULL -> Scotia", null_to_scotia),
        ("CIBC -> Scotia", cibc_to_scotia),
        ("Scotia -> CIBC", scotia_to_cibc)
    ]:
        if receipts:
            receipt_ids = [r[0] for r in receipts]
            target_id = receipts[0][5]  # All same target in group
            cur.execute("""
                UPDATE receipts
                SET mapped_bank_account_id = %s
                WHERE receipt_id = ANY(%s)
            """, (target_id, receipt_ids))
            print(f"✓ {correction_type}: {cur.rowcount} receipts")
    
    conn.commit()
    print("\n✓ All corrections applied.")
    
    # Verify
    print("\nVerifying fix...")
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id != 1
    """)
    cibc_wrong = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id != 2
    """)
    scotia_wrong = cur.fetchone()[0]
    
    total_wrong = cibc_wrong + scotia_wrong
    print(f"  CIBC txns with wrong mapping: {cibc_wrong}")
    print(f"  Scotia txns with wrong mapping: {scotia_wrong}")
    print(f"  Total remaining mismatches: {total_wrong}")
    
    if total_wrong == 0:
        print("\n✓ SUCCESS: All receipts now correctly mapped to their banking accounts.")
    else:
        print(f"\n⚠ {total_wrong} mismatches remain (receipts linked to both accounts).")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

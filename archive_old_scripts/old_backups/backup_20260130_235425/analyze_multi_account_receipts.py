#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Investigate receipts linked to BOTH CIBC and Scotia transactions."""
import os
import psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_conn()
cur = conn.cursor()

print("Analyzing receipts linked to BOTH CIBC and Scotia")
print("=" * 70)

# Find receipts linked to both accounts
cur.execute("""
    WITH receipt_accounts AS (
        SELECT r.receipt_id,
               r.vendor_name,
               r.mapped_bank_account_id,
               COUNT(DISTINCT bt.account_number) as account_count,
               STRING_AGG(DISTINCT bt.account_number, ', ') as accounts
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number IN ('0228362', '903990106011')
        GROUP BY r.receipt_id, r.vendor_name, r.mapped_bank_account_id
    )
    SELECT *
    FROM receipt_accounts
    WHERE account_count > 1
    ORDER BY receipt_id
""")
multi_account = cur.fetchall()

print(f"\nFound {len(multi_account)} receipts linked to BOTH accounts:")
for row in multi_account[:10]:
    print(f"  Receipt {row[0]} (mapped_id={row[2]}) '{row[1][:40]}' -> accounts: {row[4]}")
if len(multi_account) > 10:
    print(f"  ... and {len(multi_account) - 10} more")

# Count link types
cur.execute("""
    SELECT 
        CASE 
            WHEN bt.account_number = '0228362' THEN 'CIBC'
            WHEN bt.account_number = '903990106011' THEN 'Scotia'
        END as bank_account,
        CASE 
            WHEN r.mapped_bank_account_id = 1 THEN 'CIBC'
            WHEN r.mapped_bank_account_id = 2 THEN 'Scotia'
            ELSE 'NULL'
        END as receipt_mapped,
        COUNT(*) as link_count
    FROM banking_receipt_matching_ledger bm
    JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
    JOIN receipts r ON r.receipt_id = bm.receipt_id
    WHERE bt.account_number IN ('0228362', '903990106011')
    GROUP BY 
        CASE WHEN bt.account_number = '0228362' THEN 'CIBC' WHEN bt.account_number = '903990106011' THEN 'Scotia' END,
        CASE WHEN r.mapped_bank_account_id = 1 THEN 'CIBC' WHEN r.mapped_bank_account_id = 2 THEN 'Scotia' ELSE 'NULL' END
    ORDER BY bank_account, receipt_mapped
""")
print("\nLink breakdown:")
for row in cur.fetchall():
    status = "✓ OK" if row[0] == row[1] else "✗ WRONG"
    print(f"  {row[0]} banking -> {row[1]} receipt: {row[2]:4} links {status}")

# Count remaining mismatches
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

print(f"\nRemaining mismatches:")
print(f"  CIBC txns with wrong receipt mapping: {cibc_wrong}")
print(f"  Scotia txns with wrong receipt mapping: {scotia_wrong}")
print(f"  Total: {cibc_wrong + scotia_wrong}")

cur.close()
conn.close()

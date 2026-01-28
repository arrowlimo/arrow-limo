#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick audit: verify CIBC 0228362 and Scotia 903990106011 are not mixed."""
import os
import psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_conn()
cur = conn.cursor()

print("Per-year totals (2014-2017) for 0228362 vs 903990106011")
print("-" * 70)
cur.execute("""
    SELECT account_number,
           EXTRACT(YEAR FROM transaction_date)::int AS yr,
           COUNT(*) AS txns,
           COALESCE(SUM(debit_amount),0) AS debits,
           COALESCE(SUM(credit_amount),0) AS credits
    FROM banking_transactions
    WHERE account_number IN ('0228362','903990106011')
      AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2014 AND 2017
    GROUP BY account_number, yr
    ORDER BY account_number, yr
""")
for row in cur.fetchall():
    print(f"{row[0]:15} {row[1]} | txns: {row[2]:4} | debits: ${row[3]:12.2f} | credits: ${row[4]:12.2f}")

print("\nCross-account linkage check (receipts <-> banking)")
print("-" * 70)
cur.execute("""
    SELECT COUNT(*)
    FROM banking_receipt_matching_ledger bm
    JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
    JOIN receipts r ON r.receipt_id = bm.receipt_id
    WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id = 2
""")
cibc_to_scotia = cur.fetchone()[0]
print(f"CIBC txns linked to Scotia receipts (mapped_bank_account_id=2): {cibc_to_scotia}")

cur.execute("""
    SELECT COUNT(*)
    FROM banking_receipt_matching_ledger bm
    JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
    JOIN receipts r ON r.receipt_id = bm.receipt_id
    WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id = 1
""")
scotia_to_cibc = cur.fetchone()[0]
print(f"Scotia txns linked to CIBC receipts (mapped_bank_account_id=1): {scotia_to_cibc}")

if cibc_to_scotia > 0 or scotia_to_cibc > 0:
    print(f"\n*** ANOMALY DETECTED: {cibc_to_scotia + scotia_to_cibc} cross-account links found ***")
    print("\nSample anomalies:")
    if cibc_to_scotia > 0:
        cur.execute("""
            SELECT bt.transaction_id, bt.transaction_date, bt.description, r.receipt_id, r.vendor_name
            FROM banking_receipt_matching_ledger bm
            JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
            JOIN receipts r ON r.receipt_id = bm.receipt_id
            WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id = 2
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  CIBC txn {row[0]} ({row[1]}) '{row[2][:40]}' -> Scotia receipt {row[3]} ({row[4]})")
    
    if scotia_to_cibc > 0:
        cur.execute("""
            SELECT bt.transaction_id, bt.transaction_date, bt.description, r.receipt_id, r.vendor_name
            FROM banking_receipt_matching_ledger bm
            JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
            JOIN receipts r ON r.receipt_id = bm.receipt_id
            WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id = 1
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  Scotia txn {row[0]} ({row[1]}) '{row[2][:40]}' -> CIBC receipt {row[3]} ({row[4]})")
else:
    print("\n✓ No cross-account linkage anomalies detected.")

cur.close()
conn.close()

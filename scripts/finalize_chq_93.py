#!/usr/bin/env python3
"""Finalize CHQ 93 - mark as VOID since no banking match found"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("FINALIZE CHQ 93 - WORD OF LIFE")
print("=" * 80)

# Current state
print("\nCurrent state:")
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status, memo
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
""")

chq93 = cur.fetchone()
if chq93:
    num, date, payee, amount, tx_id, status, memo = chq93
    print(f"CHQ {num}: {payee} ${amount} | Date: {date} | Status: {status}")
    print(f"Memo: {memo}")
    print(f"TX ID: {tx_id}")

# Update CHQ 93 - set date to Nov 09, keep as VOID
print("\n" + "=" * 80)
print("UPDATING CHQ 93")
print("=" * 80)

cur.execute("""
    UPDATE cheque_register
    SET cheque_date = '2012-11-09',
        banking_transaction_id = NULL,
        status = 'VOID',
        memo = 'CHQ 93 WORD OF LIFE (DONATION) - VOID - NO BANKING RECORD'
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 93
    RETURNING cheque_number, cheque_date, payee, amount, status
""")

updated = cur.fetchone()
conn.commit()

if updated:
    num, date, payee, amount, status = updated
    print(f"✓ CHQ {num} updated:")
    print(f"  Date: {date}")
    print(f"  Payee: {payee}")
    print(f"  Amount: ${amount}")
    print(f"  Status: {status}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY - CHQ 22, 23, 93 FINAL STATUS")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23, 93)
    ORDER BY cheque_number::INTEGER
""")

for num, date, payee, amount, tx_id, status in cur.fetchall():
    tx_str = f"TX {tx_id}" if tx_id else "NO TX"
    print(f"CHQ {num:2d}: {str(date):10s} | {payee:30s} | ${amount:10.2f} | {tx_str:10s} | {status}")

print("\n✓ CHQ validation and fixes complete")

cur.close()
conn.close()

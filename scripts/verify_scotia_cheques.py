#!/usr/bin/env python3
"""Verify Scotia Bank cheques (1-117) are properly imported"""

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

# Check Scotia cheques (1-117)
cur.execute("""
    SELECT COUNT(*) as total,
           SUM(CASE WHEN cheque_date IS NOT NULL THEN 1 ELSE 0 END) as with_dates,
           SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as with_tx_id,
           SUM(CASE WHEN status = 'VOID' THEN 1 ELSE 0 END) as void_count,
           SUM(CASE WHEN status = 'NSF' THEN 1 ELSE 0 END) as nsf_count
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER BETWEEN 1 AND 117
""")

row = cur.fetchone()
print("=" * 60)
print("SCOTIA BANK CHEQUES (1-117) STATUS")
print("=" * 60)
print(f"Total Scotia cheques: {row[0]}")
print(f"With dates: {row[1]}")
print(f"Linked to banking TX: {row[2]}")
print(f"VOID cheques: {row[3]}")
print(f"NSF cheques: {row[4]}")

# Check specific cheques
print("\n" + "=" * 60)
print("SAMPLE CHEQUES (First 5 & Problem Cheques)")
print("=" * 60)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (1, 2, 3, 22, 93, 108, 117)
    ORDER BY cheque_number::INTEGER
""")

for num, date, payee, amount, tx_id, status in cur.fetchall():
    print(f"CHQ {num:3d}: {str(date):10s} {payee:25s} ${amount:10.2f} TX:{tx_id!s:>5} {status}")

# Check receipts for Scotia cheques
print("\n" + "=" * 60)
print("RECEIPTS CREATED FROM SCOTIA CHEQUES")
print("=" * 60)

cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE banking_transaction_id IN (
        SELECT banking_transaction_id 
        FROM cheque_register
        WHERE cheque_number ~ '^[0-9]+$'
          AND cheque_number::INTEGER BETWEEN 1 AND 117
          AND banking_transaction_id IS NOT NULL
    )
""")

receipt_count = cur.fetchone()[0]
print(f"Receipts created: {receipt_count}")

# Top 10 Scotia cheques by amount
print("\n" + "=" * 60)
print("TOP 10 SCOTIA CHEQUES BY AMOUNT")
print("=" * 60)

cur.execute("""
    SELECT cheque_number, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER BETWEEN 1 AND 117
    ORDER BY amount DESC
    LIMIT 10
""")

for num, payee, amount, tx_id, status in cur.fetchall():
    print(f"CHQ {num:3d}: {payee:25s} ${amount:10.2f} {status}")

print("\n✓ Scotia cheques verification complete")

cur.close()
conn.close()

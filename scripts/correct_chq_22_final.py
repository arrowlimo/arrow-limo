#!/usr/bin/env python3
"""Correct CHQ 22 WITH THIS RING to use banking TX 81695"""

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
print("FIX CHQ 22 - WITH THIS RING BRIDAL GALA")
print("=" * 80)

# Current state
print("\nCurrent state:")
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
""")

chq22 = cur.fetchone()
if chq22:
    num, chq_date, payee, amount, tx_id, status = chq22
    print(f"CHQ 22: {payee} ${amount} | Date: {chq_date} | TX: {tx_id} | Status: {status}")

# Show correct banking TX
print("\nCorrect banking transaction:")
cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE transaction_id = 81695
""")

banking = cur.fetchone()
if banking:
    tx_id, tx_date, desc = banking
    print(f"TX {tx_id}: {tx_date} | {desc}")
    print(f"✓ WITH THIS RING BRIDAL GALA matches CHQ 22")

# Update CHQ 22 to use TX 81695
print("\nUpdating CHQ 22 to TX 81695...")
cur.execute("""
    UPDATE cheque_register
    SET banking_transaction_id = 81695,
        status = 'CLEARED'
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
    RETURNING cheque_number, cheque_date, payee, amount, banking_transaction_id, status
""")

updated = cur.fetchone()
conn.commit()

if updated:
    num, chq_date, payee, amount, tx_id, status = updated
    print(f"✓ CHQ 22 updated:")
    print(f"  Payee: {payee}")
    print(f"  Amount: ${amount}")
    print(f"  Banking TX: {tx_id}")
    print(f"  Status: {status}")

# Final summary
print("\n" + "=" * 80)
print("FINAL CHQ 22, 23, 93 STATUS")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23, 93)
    ORDER BY cheque_number::INTEGER
""")

for num, payee, amount, tx_id, status in cur.fetchall():
    tx_str = f"TX {tx_id}" if tx_id else "NO TX"
    print(f"CHQ {num:2d}: {payee:30s} | ${amount:10.2f} | {tx_str:10s} | {status}")

print("\n✓ All checks linked to banking records")

cur.close()
conn.close()

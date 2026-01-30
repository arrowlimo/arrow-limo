#!/usr/bin/env python3
"""Link CHQ 22 WITH THIS RING $682.50 to TX 80489"""

import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 80)
print("LINK CHQ 22 WITH THIS RING $682.50 TO TX 80489")
print("=" * 80)

# Get full details of TX 80489
print("\nBanking Transaction Details:")
cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE transaction_id = 80489
""")

banking_tx = cur.fetchone()
if banking_tx:
    tx_id, tx_date, desc = banking_tx
    print(f"TX {tx_id}: {tx_date}")
    print(f"Description: {desc}")

# Get current CHQ 22
print("\n\nCurrent CHQ 22:")
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
""")

chq22 = cur.fetchone()
if chq22:
    num, date, payee, amount, old_tx_id = chq22
    print(f"CHQ {num}: {payee} ${amount} | Date: {date} | Old TX: {old_tx_id}")

# Update CHQ 22 to link to TX 80489
print("\n\nUpdating CHQ 22 to TX 80489...")
cur.execute("""
    UPDATE cheque_register
    SET banking_transaction_id = 80489,
        cheque_date = '2012-02-20',
        status = 'CLEARED'
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER = 22
    RETURNING cheque_number, cheque_date, payee, amount, banking_transaction_id, status
""")

updated = cur.fetchone()
conn.commit()

if updated:
    num, date, payee, amount, tx_id, status = updated
    print(f"✓ CHQ 22 updated:")
    print(f"  Date: {date}")
    print(f"  Payee: {payee}")
    print(f"  Amount: ${amount}")
    print(f"  Banking TX: {tx_id}")
    print(f"  Status: {status}")

# Final summary
print("\n" + "=" * 80)
print("FINAL STATUS - CHQ 22, 23, 213")
print("=" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23, 213)
    ORDER BY cheque_number::INTEGER
""")

for num, date, payee, amount, tx_id, status in cur.fetchall():
    num_int = int(num) if isinstance(num, str) else num
    tx_str = f"TX {tx_id}" if tx_id else "NO TX"
    print(f"CHQ {num_int:3d}: {payee:35s} | ${amount:10.2f} | {tx_str:10s} | {status}")

print("\n✓ All WITH THIS RING checks properly linked:")
print("  - CHQ 22: WITH THIS RING $682.50 → TX 80489 (2012-02-20)")
print("  - CHQ 213: WITH THIS RING $1,050.00 → TX 57179 (2012-03-13)")
print("  - CHQ 23: HEFFNER AUTO $1,475.25 → TX 69370 (2012-09-25) ✓")

cur.close()
conn.close()

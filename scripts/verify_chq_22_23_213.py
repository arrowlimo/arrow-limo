#!/usr/bin/env python3
"""Check CHQ 22, 23, 213 current state in database"""

import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

print("=" * 80)
print("CHECK CHQ 22, 23, 213 - CURRENT DATABASE STATE")
print("=" * 80)

# Get CHQ 22, 23, and 213
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23, 213)
    ORDER BY cheque_number::INTEGER
""")

cheques = cur.fetchall()
print("\nCurrent database state:")
for num, date, payee, amount, tx_id, status in cheques:
    tx_str = f"TX {tx_id}" if tx_id else "NO TX"
    num_int = int(num) if isinstance(num, str) else num
    print(f"CHQ {num_int:3d}: {str(date):10s} | {payee:35s} | ${amount:10.2f} | {tx_str:10s} | {status}")

# Show banking records for these check numbers
print("\n" + "=" * 80)
print("WHAT DO BANKING RECORDS SHOW FOR THESE CHECK NUMBERS?")
print("=" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%CHQ 22%'
       OR description ILIKE '%CHQ 23%'
       OR description ILIKE '%CHQ 213%'
    ORDER BY transaction_date
""")

banking_matches = cur.fetchall()
if banking_matches:
    print(f"\nFound {len(banking_matches)} banking records:")
    for tx_id, tx_date, desc in banking_matches:
        print(f"  TX {tx_id}: {tx_date} | {desc}")
else:
    print("\nNo banking records found with CHQ 22, 23, or 213 in description")

print("\n" + "=" * 80)
print("QUESTION FOR YOU:")
print("=" * 80)
print("""
Current database shows:
- CHQ 22: WITH THIS RING $682.50 (in database)
- CHQ 23: HEFFNER AUTO $1,475.25 (in database)
- CHQ 213: WITH THIS RING BRIDAL $1,050.00 (in database)

Banking shows:
- CHQ 213 WITH THIS RING BRIDAL GALA (TX 81695)
- CHQ 23 HEFFNER AUTO (mentioned in descriptions)

Did you perhaps mistype CHQ 23 when it should be something else?
Or is CHQ 23 supposed to be HEFFNER as shown?
""")

cur.close()
conn.close()

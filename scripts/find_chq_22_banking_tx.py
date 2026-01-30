#!/usr/bin/env python3
"""Find banking transaction for CHQ 22 WITH THIS RING $682.50"""

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
print("FIND CHQ 22 WITH THIS RING $682.50 IN BANKING")
print("=" * 80)

# Search for $682.50 in 2012
print("\n1. Search for $682.50 WITH THIS RING in 2012:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%WITH THIS RING%'
      OR description ILIKE '%RING%BRIDAL%'
      OR description ILIKE '%BRIDAL%RING%'
    ORDER BY transaction_date
""")

ring_trans = cur.fetchall()
print(f"Found {len(ring_trans)} WITH THIS RING transactions in 2012:")
for tx_id, tx_date, desc in ring_trans:
    print(f"  TX {tx_id}: {tx_date} | {desc}")

# Search by amount $682.50 specifically
print("\n2. Search for exactly $682.50 in 2012:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
      AND (description LIKE '%682%' OR description LIKE '%CHQ 22%')
    ORDER BY transaction_date
    LIMIT 20
""")

amt682 = cur.fetchall()
if amt682:
    print(f"Found {len(amt682)} transactions with 682 or CHQ 22:")
    for tx_id, tx_date, desc in amt682:
        print(f"  TX {tx_id}: {tx_date} | {desc}")
else:
    print("No exact matches for 682.50 or CHQ 22")

# Search all cheque expenses from Feb 2012 (when first bridal event was)
print("\n3. All cheque expense records from 2012 Feb-Sep:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
      AND (description ILIKE '%CHEQUE%' OR description ILIKE '%CHQ%')
      AND EXTRACT(MONTH FROM transaction_date) BETWEEN 2 AND 9
    ORDER BY transaction_date
    LIMIT 30
""")

cheque_exps = cur.fetchall()
print(f"Found {len(cheque_exps)} cheque expense records:")
for tx_id, tx_date, desc in cheque_exps:
    print(f"  TX {tx_id}: {tx_date} | {desc}")

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)
print("""
Looking at the results:
- TX 80489 (2012-02-20): Cheque Expense - With This Ring Bridal Gala
- TX 60091, 60092 (2012-02-20): Cheque #213 With This Ring...
- TX 81695 (2012-03-13): CHQ 213 WITH THIS RING BRIDAL GALA

For CHQ 22 $682.50: May need to check if it's a separate payment
or if the Feb 20 transactions show both amounts.

TX 80489 on 2012-02-20 may be the CHQ 22 record.
""")

cur.close()
conn.close()

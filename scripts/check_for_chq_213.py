#!/usr/bin/env python3
"""Check if CHQ 213 exists in cheque_register and its details"""

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
print("SEARCH FOR CHQ 213 IN DATABASE")
print("=" * 80)

# Search for CHQ 213 in cheque register
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number LIKE '%213%'
""")

results = cur.fetchall()
if results:
    print(f"\nFound {len(results)} cheque(s) with '213':")
    for num, date, payee, amount, tx_id, status in results:
        print(f"  CHQ {num}: {payee} ${amount} | Date: {date} | TX: {tx_id} | Status: {status}")
else:
    print("\nNo CHQ 213 found in cheque_register")

# Summary for the user
print("\n" + "=" * 80)
print("YOUR QUESTION:")
print("=" * 80)
print("""
CHQ 213 = WITH THIS RING $1,050.00 (in banking records)
CHQ 22 = WITH THIS RING $682.50 (in your register)

Banking shows:
- TX 81695 (2012-03-13): CHQ 213 WITH THIS RING BRIDAL GALA
- This is different from CHQ 22

So your register has TWO checks:
1. CHQ 22: WITH THIS RING $682.50
2. CHQ 213: WITH THIS RING $1,050.00 (NOT YET IN DATABASE)

Do you have CHQ 213 with $1,050.00 in your hand-written register?
""")

cur.close()
conn.close()

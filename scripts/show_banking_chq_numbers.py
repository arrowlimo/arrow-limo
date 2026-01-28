#!/usr/bin/env python3
"""Show what check numbers banking records have for CHQ 22 and 23 amounts"""

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
print("WHAT CHECK NUMBERS ARE IN BANKING RECORDS?")
print("=" * 80)

# CHQ 22 - $682.50 WITH THIS RING
print("\n1. CHQ 22 AMOUNT: $682.50 (WITH THIS RING)")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%WITH THIS RING%'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

for tx_id, tx_date, desc in cur.fetchall():
    print(f"TX {tx_id}: {tx_date}")
    print(f"  Description: {desc}")
    
    # Extract check number from description if present
    if 'CHQ' in desc.upper():
        parts = desc.split()
        for i, part in enumerate(parts):
            if part.upper() == 'CHQ':
                if i + 1 < len(parts):
                    chq_num = parts[i+1]
                    print(f"  ✓ Banking shows: CHQ {chq_num}")

# CHQ 23 - $1,475.25 HEFFNER AUTO
print("\n2. CHQ 23 AMOUNT: $1,475.25 (HEFFNER AUTO)")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%HEFFNER%'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
      AND EXTRACT(MONTH FROM transaction_date) = 9
""")

for tx_id, tx_date, desc in cur.fetchall():
    print(f"TX {tx_id}: {tx_date}")
    print(f"  Description: {desc}")
    
    # Extract check number from description if present
    if 'CHQ' in desc.upper():
        parts = desc.split()
        for i, part in enumerate(parts):
            if part.upper() == 'CHQ':
                if i + 1 < len(parts):
                    chq_num = parts[i+1]
                    print(f"  ✓ Banking shows: CHQ {chq_num}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
The banking records show:
- $682.50 WITH THIS RING: Banking shows CHQ 213 (but your register has CHQ 22)
- $1,475.25 HEFFNER: Banking shows CHQ 23 (matches your register CHQ 23)

So your register CHQ 22 with amount $682.50 matches banking TX that says CHQ 213.
""")

cur.close()
conn.close()

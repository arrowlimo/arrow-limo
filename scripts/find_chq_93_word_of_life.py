#!/usr/bin/env python3
"""Find CHQ 93 Word of Life $200 donation - search all of Nov 2012"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("SEARCH FOR CHQ 93 - WORD OF LIFE $200")
print("=" * 80)

# Search for $200 in Nov 2012
print("\nAll Nov 2012 banking entries for $200.00:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE EXTRACT(MONTH FROM transaction_date) = 11
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, transaction_id
""")

all_nov = cur.fetchall()
for tx_id, tx_date, desc in all_nov:
    if '200' in desc or '0.00' in desc or 'LIFE' in desc.upper():
        print(f"TX {tx_id}: {tx_date} | {desc}")

print("\n\nSearching for 'LIFE' or 'DONATION' anywhere in Nov-Dec 2012:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE (description ILIKE '%LIFE%' OR description ILIKE '%DONAT%')
      AND EXTRACT(YEAR FROM transaction_date) IN (2012, 2013)
    ORDER BY transaction_date
""")

life_matches = cur.fetchall()
for tx_id, tx_date, desc in life_matches:
    print(f"TX {tx_id}: {tx_date} | {desc}")

if not life_matches:
    print("No 'LIFE' or 'DONAT' transactions found")

# Search for $200 in entire 2012
print("\n\nAll 2012 transactions for exactly $200.00:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
      AND description LIKE '%200%'
    ORDER BY transaction_date
""")

amt200 = cur.fetchall()
count = 0
for tx_id, tx_date, desc in amt200:
    print(f"TX {tx_id}: {tx_date} | {desc}")
    count += 1
    if count > 20:
        print("... (truncated)")
        break

print("\n" + "=" * 80)
print("NOTE: CHQ 93 may not have a banking record (donation, not standard payment)")
print("=" * 80)

cur.close()
conn.close()

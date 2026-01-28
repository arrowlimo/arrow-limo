#!/usr/bin/env python3
"""Find correct WITH THIS RING banking TX from 2012"""

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
print("FIND CORRECT WITH THIS RING TX FROM 2012")
print("=" * 80)

# Search for WITH THIS RING in 2012 specifically
print("\n2012 transactions with 'RING', 'BRIDAL', 'GALA':")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
      AND (description ILIKE '%RING%' OR description ILIKE '%BRIDAL%' OR description ILIKE '%GALA%')
    ORDER BY transaction_date DESC
""")

matches_2012 = cur.fetchall()
if matches_2012:
    print(f"Found {len(matches_2012)} transactions in 2012:")
    for tx_id, tx_date, desc in matches_2012:
        print(f"  TX {tx_id}: {tx_date} | {desc}")
        
        if tx_id == 81695:
            print(f"    ^ This is likely the correct one (CHQ 213 bridal)")
else:
    print("No matches found")

# Also check September 2012 range for bridal events
print("\n\nAll Sep 2012 transactions:")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE EXTRACT(MONTH FROM transaction_date) = 9
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
    LIMIT 30
""")

sep_trans = cur.fetchall()
print(f"Found {len(sep_trans)} Sep 2012 transactions:")
for tx_id, tx_date, desc in sep_trans:
    print(f"  TX {tx_id}: {tx_date} | {desc}")

cur.close()
conn.close()

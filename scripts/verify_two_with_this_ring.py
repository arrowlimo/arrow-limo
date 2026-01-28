#!/usr/bin/env python3
"""Verify both WITH THIS RING checks - CHQ 22 $682.50 and CHQ 213 $1,050.00"""

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
print("VERIFY TWO WITH THIS RING CHECKS IN BANKING")
print("=" * 80)

# Search for $682.50 WITH THIS RING
print("\n1. CHQ 22 - WITH THIS RING $682.50")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%WITH THIS RING%'
      AND description ILIKE '%BRIDAL%'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")

bridal_matches = cur.fetchall()
print(f"Found {len(bridal_matches)} WITH THIS RING BRIDAL transactions:")
for tx_id, tx_date, desc in bridal_matches:
    print(f"  TX {tx_id}: {tx_date} | {desc}")

# Search for $1,050.00 WITH THIS RING
print("\n2. CHQ 213 - WITH THIS RING $1,050.00")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description ILIKE '%WITH THIS RING%'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")

all_ring_matches = cur.fetchall()
print(f"All WITH THIS RING transactions in 2012:")
for tx_id, tx_date, desc in all_ring_matches:
    print(f"  TX {tx_id}: {tx_date} | {desc}")

# Check specifically for 682.50 and 1050.00
print("\n" + "=" * 80)
print("SEARCH BY AMOUNTS")
print("=" * 80)

print("\n$682.50 transactions:")
cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description LIKE '%682%' OR description LIKE '%682.50%'
""")

for tx_id, tx_date, desc in cur.fetchall():
    print(f"  TX {tx_id}: {tx_date} | {desc}")

print("\n$1,050.00 transactions:")
cur.execute("""
    SELECT transaction_id, transaction_date, description
    FROM banking_transactions
    WHERE description LIKE '%1050%' OR description LIKE '%1,050%'
""")

for tx_id, tx_date, desc in cur.fetchall():
    print(f"  TX {tx_id}: {tx_date} | {desc}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

cur.close()
conn.close()

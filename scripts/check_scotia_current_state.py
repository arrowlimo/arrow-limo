#!/usr/bin/env python
"""Check current state of Scotia account in database."""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("SCOTIA BANK CURRENT DATABASE STATE")
print("=" * 80)

# Check each year
for year in [2012, 2013, 2014]:
    print(f"\n{year}:")
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as has_balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    stats = cur.fetchone()
    if stats[0] == 0:
        print(f"  No records found")
        continue
    
    print(f"  Total records: {stats[0]}")
    print(f"  Date range: {stats[1]} to {stats[2]}")
    print(f"  Records with balance: {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")
    
    # Get opening balance
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        AND balance IS NOT NULL
        ORDER BY transaction_date, transaction_id
        LIMIT 1
    """, (year,))
    
    opening = cur.fetchone()
    if opening:
        print(f"  Opening: {opening[0]} - ${float(opening[1]):.2f}")
    
    # Get closing balance
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        AND balance IS NOT NULL
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    """, (year,))
    
    closing = cur.fetchone()
    if closing:
        print(f"  Closing: {closing[0]} - ${float(closing[1]):.2f}")

print("\n" + "=" * 80)

# Expected values
print("\nEXPECTED BALANCES (from user):")
print("  2012: $40.00 → $952.04")
print("  2013: $952.04 → $6,404.87")
print("  2014: $1,839.42 → $4,006.29")

cur.close()
conn.close()

#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT account_number 
    FROM banking_transactions 
    WHERE account_number LIKE '367%' OR account_number LIKE '377%'
    ORDER BY account_number
""")

print("Scotia-like account numbers:")
for row in cur.fetchall():
    print(f"  {row[0]}")

print("\nYear breakdown by account:")
cur.execute("""
    SELECT 
        account_number,
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count
    FROM banking_transactions 
    WHERE account_number LIKE '367%' OR account_number LIKE '377%'
    GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
    ORDER BY account_number, year
""")

current_account = None
for acct, year, count in cur.fetchall():
    if acct != current_account:
        print(f"\nAccount {acct}:")
        current_account = acct
    print(f"  {int(year)}: {count:,} transactions")

conn.close()

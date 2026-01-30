#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount 
    FROM banking_transactions 
    WHERE account_number = '1615' 
        AND debit_amount > 0 
        AND receipt_id IS NULL 
    ORDER BY transaction_date
""")

print("CIBC 1615 Unmatched Transactions:")
print("=" * 90)
for txn_id, date, desc, amount in cur.fetchall():
    desc_str = f"'{desc}'" if desc else "(blank)"
    print(f"{txn_id:6d} | {date} | {desc_str:50s} | ${amount:9,.2f}")

conn.close()

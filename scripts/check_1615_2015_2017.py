#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    user='postgres', 
    password='***REMOVED***',
    database='almsdata'
)
cur = conn.cursor()

# Check summary by year
cur.execute("""
    SELECT EXTRACT(YEAR FROM transaction_date) as year, COUNT(*) as txn_count, 
           MIN(transaction_date) as first_date, MAX(transaction_date) as last_date,
           SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
           SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions 
    WHERE account_number = '61615' 
    GROUP BY EXTRACT(YEAR FROM transaction_date) 
    ORDER BY year
""")

print("CIBC Account 1615 Summary:")
for row in cur.fetchall():
    year, count, first, last, debits, credits = row
    if row[0] is not None:
        print(f"  {int(year)}: {count} txns, {first} to {last}")
        print(f"       Debits: ${debits if debits else 0:.2f}, Credits: ${credits if credits else 0:.2f}")

# Check January 2015
print("\nJanuary 2015 transactions:")
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '61615' AND EXTRACT(YEAR FROM transaction_date) = 2015 AND EXTRACT(MONTH FROM transaction_date) = 1
    ORDER BY transaction_date
""")
jan_2015 = cur.fetchall()
if jan_2015:
    for row in jan_2015:
        desc = (row[1][:40] if row[1] else "")
        print(f"  {row[0]}: {desc:40s} D:{row[2]:10.2f} C:{row[3]:10.2f} Bal:{row[4]:12.2f}")
else:
    print("  (No data found)")

# Check January 2016
print("\nJanuary 2016 transactions:")
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '61615' AND EXTRACT(YEAR FROM transaction_date) = 2016 AND EXTRACT(MONTH FROM transaction_date) = 1
    ORDER BY transaction_date
""")
jan_2016 = cur.fetchall()
if jan_2016:
    for row in jan_2016:
        desc = (row[1][:40] if row[1] else "")
        print(f"  {row[0]}: {desc:40s} D:{row[2]:10.2f} C:{row[3]:10.2f} Bal:{row[4]:12.2f}")
else:
    print("  (No data found)")

# Check for -4221.09 opening balance (Jan 1 2015) and -5197.99 opening (Jan 1 2016)
print("\nSearching for specific balances:")
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '61615' 
    AND (balance = -4221.09 OR balance = -5197.99 OR balance = -4296.38)
    ORDER BY transaction_date
""")
for row in cur.fetchall():
    desc = (row[1][:40] if row[1] else "")
    print(f"  {row[0]}: {desc:40s} Bal:{row[4]:12.2f}")

cur.close()
conn.close()

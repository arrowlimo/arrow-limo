#!/usr/bin/env python3
"""Check Scotia Bank 2013 data currently in database"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        EXTRACT(MONTH FROM transaction_date)::int as month, 
        COUNT(*), 
        SUM(debit_amount), 
        SUM(credit_amount) 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND EXTRACT(YEAR FROM transaction_date) = 2013 
    GROUP BY EXTRACT(MONTH FROM transaction_date) 
    ORDER BY month
""")

rows = cur.fetchall()

print('\nScotia Bank 2013 - Current Database:\n')
print(f"{'Month':<10} {'Count':>8} {'Debits':>15} {'Credits':>15}")
print('-'*50)

total_txns = 0
total_debits = 0
total_credits = 0

for month, count, debits, credits in rows:
    print(f"{month:02d}/2013    {count:>8} ${debits or 0:>13,.2f} ${credits or 0:>13,.2f}")
    total_txns += count
    total_debits += float(debits or 0)
    total_credits += float(credits or 0)

print('-'*50)
print(f"{'TOTAL':<10} {total_txns:>8} ${total_debits:>13,.2f} ${total_credits:>13,.2f}")

cur.close()
conn.close()

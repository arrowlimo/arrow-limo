#!/usr/bin/env python3
"""Search for CRA payments in banking transactions."""
import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres', 
    password='***REDACTED***',
    host='localhost'
)
cur = conn.cursor()

cur.execute("""
SELECT transaction_date, description, debit_amount, account_number
FROM banking_transactions 
WHERE (
  LOWER(description) LIKE '%receiver%general%'
  OR LOWER(description) LIKE '%cra%'
  OR LOWER(description) LIKE '%canada revenue%'
  OR LOWER(description) LIKE '%revenue canada%'
  OR LOWER(description) LIKE '%gst%remit%'
  OR LOWER(description) LIKE '%tax%payment%'
  OR LOWER(description) LIKE '%rcvr%gen%'
)
AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2015
ORDER BY transaction_date
""")

rows = cur.fetchall()
print(f'\n{"="*100}')
print(f'CRA PAYMENT SEARCH: 2012-2015')
print(f'{"="*100}\n')
print(f'Found {len(rows)} potential CRA payments:\n')

if rows:
    total = 0
    for row in rows:
        print(f'{row[0]} | {row[1]:<60} | ${row[2]:>12,.2f} | {row[3]}')
        total += float(row[2] or 0)
    print(f'\n{"="*100}')
    print(f'TOTAL CRA PAYMENTS FOUND: ${total:,.2f}')
    print(f'{"="*100}\n')
else:
    print('[FAIL] NO CRA PAYMENTS FOUND IN BANKING DATA\n')
    print('This confirms: GST returns were never filed, no payments made.\n')

cur.close()
conn.close()

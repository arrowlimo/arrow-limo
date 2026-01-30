import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== ALL BANKING TRANSACTIONS on 2012-09-17 ===')
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, transaction_id, account_number
    FROM banking_transactions
    WHERE transaction_date = '2012-09-17'
    ORDER BY transaction_id
""")
all_sept17 = cur.fetchall()
print(f'\nTotal transactions on Sept 17: {len(all_sept17)}')
for row in all_sept17:
    amt = row[2] if row[2] else -row[3]
    print(f'{row[0]} | {row[1][:60]:60} | ${amt:8.2f} | ID:{row[4]} | Acct:{row[5]}')

print('\n=== ALL RECEIPTS on 2012-09-17 (gas stations) ===')
cur.execute("""
    SELECT receipt_date, vendor_name, canonical_vendor, gross_amount, description, receipt_id, banking_transaction_id
    FROM receipts
    WHERE receipt_date = '2012-09-17'
      AND (UPPER(vendor_name) LIKE '%SHELL%' 
           OR UPPER(canonical_vendor) LIKE '%SHELL%'
           OR UPPER(vendor_name) LIKE '%GAS%'
           OR UPPER(vendor_name) LIKE '%PETRO%'
           OR UPPER(vendor_name) LIKE '%FISHER%'
           OR UPPER(vendor_name) LIKE '%RUN%EMPTY%')
    ORDER BY receipt_id
""")
receipts = cur.fetchall()
print(f'\nTotal gas station receipts on Sept 17: {len(receipts)}')
for row in receipts:
    banking_id = row[6] if row[6] else 'NOT LINKED'
    print(f'{row[0]} | {row[1][:30]:30} | Can:{row[2] or "none":20} | ${row[3]:8.2f} | Banking:{banking_id} | RID:{row[5]}')

print('\n=== SEARCH: transactions with ONTARIO or SHELL ===')
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, transaction_id
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-09-10' AND '2012-09-24'
      AND (UPPER(description) LIKE '%ONTARIO%' OR UPPER(description) LIKE '%SHELL%')
    ORDER BY transaction_date
""")
ontario_shell = cur.fetchall()
print(f'\nTotal with ONTARIO or SHELL: {len(ontario_shell)}')
for row in ontario_shell:
    amt = row[2] if row[2] else -row[3]
    print(f'{row[0]} | {row[1][:70]:70} | ${amt:8.2f} | ID:{row[4]}')

cur.close()
conn.close()

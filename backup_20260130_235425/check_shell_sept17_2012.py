import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Check banking transactions for Shell around Sept 17, 2012
print('=== BANKING TRANSACTIONS - Shell around Sept 17, 2012 ===')
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, bank_id, transaction_id
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-09-10' AND '2012-09-24'
      AND UPPER(description) LIKE '%SHELL%'
    ORDER BY transaction_date
""")
banking = cur.fetchall()
if banking:
    for row in banking:
        amt = row[2] if row[2] else -row[3]  # debit positive, credit negative
        print(f'{row[0]} | {row[1][:50]:50} | ${amt:8.2f} | Bank:{row[4]} | ID:{row[5]}')
else:
    print('No Shell banking transactions found in that period')

print('\n=== RECEIPTS - Shell around Sept 17, 2012 ===')
cur.execute("""
    SELECT receipt_date, vendor_name, gross_amount, description, receipt_id, banking_transaction_id
    FROM receipts
    WHERE receipt_date BETWEEN '2012-09-10' AND '2012-09-24'
      AND (UPPER(vendor_name) LIKE '%SHELL%' OR UPPER(canonical_vendor) LIKE '%SHELL%')
    ORDER BY receipt_date
""")
receipts = cur.fetchall()
if receipts:
    for row in receipts:
        banking_id = row[5] if row[5] else 'NOT LINKED'
        print(f'{row[0]} | {row[1][:30]:30} | ${row[2]:8.2f} | Banking:{banking_id} | Receipt ID:{row[4]}')
else:
    print('No Shell receipts found in that period')

print('\n=== ALL SCOTIA BANKING Sept 10-24, 2012 (for context) ===')
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, transaction_id
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-09-10' AND '2012-09-24'
      AND bank_id = 2
    ORDER BY transaction_date
""")
all_scotia = cur.fetchall()
print(f'\nTotal Scotia transactions in period: {len(all_scotia)}')
for row in all_scotia[:30]:
    amt = row[2] if row[2] else -row[3]
    print(f'{row[0]} | {row[1][:60]:60} | ${amt:8.2f} | ID:{row[4]}')
if len(all_scotia) > 30:
    print(f'... and {len(all_scotia) - 30} more')

cur.close()
conn.close()

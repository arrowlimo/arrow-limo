import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    database=os.getenv('DB_NAME', 'almsdata')
)
cur = conn.cursor()

print('='*80)
print('JANUARY 31, 2012 - ACCOUNT 1615 CLOSING BALANCE')
print('='*80)
print()

# Check last transaction in January 2012
cur.execute('''
    SELECT 
        transaction_date,
        description,
        balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 1
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
''')

row = cur.fetchone()
if row:
    date, desc, balance = row
    print(f'Last January 2012 transaction in database:')
    print(f'  Date: {date}')
    print(f'  Description: {desc}')
    print(f'  Balance: ${balance:.2f}')
    print()
    print(f'Correct balance from PDF statement: $-49.17')
    print()
    if abs(balance - (-49.17)) < 0.01:
        print('✅ DATABASE MATCHES PDF')
    else:
        print(f'❌ MISMATCH - Difference: ${balance - (-49.17):.2f}')
else:
    print('NO JANUARY 2012 TRANSACTIONS FOUND')

conn.close()

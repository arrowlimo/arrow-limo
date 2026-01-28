import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    database=os.getenv('DB_NAME', 'almsdata')
)
cur = conn.cursor()

print('='*70)
print('JANUARY 2012 - ACCOUNT 1615 BALANCE ANALYSIS')
print('='*70)
print()
print('EXPECTED 2011 CLOSING (Dec 31, 2011): $7,177.34')
print()

cur.execute('''
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 1
    ORDER BY transaction_date, transaction_id
''')

results = cur.fetchall()
if results:
    print(f'FOUND {len(results)} TRANSACTIONS IN JANUARY 2012:')
    print()
    
    first_row = results[0]
    print(f'FIRST TRANSACTION:')
    print(f'  Date: {first_row[0]}')
    print(f'  Description: {first_row[1]}')
    print(f'  Balance: {first_row[4]:.2f}')
    print()
    
    if first_row[4] != 7177.34:
        print(f'⚠️ PROBLEM: First balance is ${first_row[4]:.2f}, NOT $7,177.34')
        print(f'   Difference: ${7177.34 - first_row[4]:.2f}')
    else:
        print(f'✅ CORRECT: First balance matches Dec 31, 2011 closing')
    
    print()
    print('ALL JANUARY 2012 TRANSACTIONS:')
    print('-'*70)
    for row in results:
        date, desc, debit, credit, balance = row
        amount = debit if debit else credit
        direction = 'OUT' if debit else 'IN '
        print(f'{str(date)} | {direction} {amount:12,.2f} | Bal: {balance:12,.2f} | {desc[:35]}')
    
    print()
    last_row = results[-1]
    print(f'LAST BALANCE IN JANUARY 2012: ${last_row[4]:.2f}')
    print(f'Date: {last_row[0]}')
else:
    print('NO JANUARY 2012 TRANSACTIONS FOUND!')

# Check if there's more data after January
print()
print('='*70)
print('REST OF 2012 - ACCOUNT 1615')
print('='*70)

cur.execute('''
    SELECT 
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY month
    ORDER BY month
''')

results = cur.fetchall()
for row in results:
    month, count, first_date, last_date = row
    print(f'  Month {int(month):2d}: {count:3d} txns | {first_date} to {last_date}')

conn.close()

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
print('ACCOUNT 1615 - 2012 FULL YEAR BREAKDOWN BY MONTH')
print('='*80)
print()

cur.execute('''
    SELECT 
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as transaction_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        MIN(balance) as min_balance,
        MAX(balance) as max_balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY month
    ORDER BY month
''')

results = cur.fetchall()

month_names = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

total_txns = 0
for row in results:
    month, count, first_date, last_date, min_bal, max_bal = row
    month_name = month_names[int(month)]
    total_txns += count
    print(f'{month_name} ({int(month):2d}): {count:4d} txns | {first_date} to {last_date} | Balance range: {min_bal:10.2f} to {max_bal:10.2f}')

print()
print(f'TOTAL 2012 TRANSACTIONS: {total_txns}')
print()

# Get Dec 31 closing balance
cur.execute('''
    SELECT balance FROM banking_transactions
    WHERE account_number = '1615'
    AND transaction_date = '2012-12-31'
    ORDER BY transaction_id DESC
    LIMIT 1
''')

dec_31 = cur.fetchone()
if dec_31:
    print(f'DEC 31, 2012 CLOSING BALANCE: ${dec_31[0]:.2f}')
else:
    print('NO DEC 31 CLOSING BALANCE FOUND')
    
    # Try to find the last transaction in 2012
    cur.execute('''
        SELECT transaction_date, description, balance 
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    ''')
    
    last = cur.fetchone()
    if last:
        print(f'Last 2012 transaction: {last[0]} | {last[1]} | Balance: ${last[2]:.2f}')

conn.close()

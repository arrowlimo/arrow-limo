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
print('ACCOUNT 1615 - FULL 2012 DATA (AFTER TODAY IMPORT AND VALIDATION)')
print('='*80)
print()

cur.execute('''
    SELECT 
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        MIN(balance) as min_bal,
        MAX(balance) as max_bal
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY month
    ORDER BY month
''')

results = cur.fetchall()

if results:
    month_names = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    total_txns = 0
    
    for row in results:
        month, count, first_date, last_date, min_bal, max_bal = row
        month_name = month_names[int(month)]
        total_txns += count
        print(f'{month_name}: {count:4d} txns | {first_date} to {last_date} | Balance: {min_bal:10.2f} to {max_bal:10.2f}')
    
    print()
    print(f'TOTAL 2012 TRANSACTIONS: {total_txns}')
    print()
    
    # Get 2012 closing balance
    cur.execute('''
        SELECT balance FROM banking_transactions
        WHERE account_number = '1615'
        AND transaction_date <= '2012-12-31'
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    ''')
    
    closing = cur.fetchone()
    if closing:
        print(f'2012 CLOSING BALANCE (DEC 31): {closing[0]:.2f}')
else:
    print('NO 2012 DATA FOUND')

conn.close()

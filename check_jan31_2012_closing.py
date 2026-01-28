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
print('JANUARY 31, 2012 - ACCOUNT 1615 (DATABASE vs PDF)')
print('='*80)
print()

cur.execute('''
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 1
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 10
''')

results = cur.fetchall()
print('LAST 10 TRANSACTIONS IN JANUARY 2012 (DATABASE):')
print('-'*80)

for row in results:
    txn_id, date, desc, debit, credit, balance = row
    debit_str = f"{debit:>10.2f}" if debit else "          "
    credit_str = f"{credit:>10.2f}" if credit else "          "
    balance_str = f"{balance:>10.2f}" if balance else "NULL      "
    print(f'{str(date)} | {desc[:35]:<35} | Debit: {debit_str} | Credit: {credit_str} | Bal: {balance_str}')

print()
print('='*80)
print('JANUARY 31, 2012 CLOSING BALANCE COMPARISON')
print('='*80)
print()

# Get the last transaction's balance
cur.execute('''
    SELECT balance FROM banking_transactions
    WHERE account_number = '1615'
    AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
''')

result = cur.fetchone()
db_balance = result[0] if result else None

print(f'PDF Statement Closing Balance (Jan 31, 2012): -$49.17')
print(f'Database Closing Balance (Jan 31, 2012):      ${db_balance:.2f}')
print()

if db_balance is not None:
    if abs(db_balance - (-49.17)) < 0.01:
        print('✅ MATCH - Database and PDF balances are correct!')
    else:
        difference = db_balance - (-49.17)
        print(f'❌ MISMATCH - Difference: ${difference:.2f}')
        print(f'   Database is off by ${difference:.2f}')
else:
    print('❌ ERROR - No balance found in database for January 2012')

conn.close()

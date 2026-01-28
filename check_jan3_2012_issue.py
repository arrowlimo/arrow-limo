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
print('JANUARY 3, 2012 - ACCOUNT 1615 TRANSACTIONS (DATABASE)')
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
    AND transaction_date = '2012-01-03'
    ORDER BY transaction_id
''')

results = cur.fetchall()
print(f'TOTAL TRANSACTIONS ON JAN 3: {len(results)}')
print()
print('-'*80)
print(f'{"ID":>4} | {"Date":<12} | {"Description":<35} | {"Debit":>10} | {"Credit":>10} | {"Balance":>12}')
print('-'*80)

for row in results:
    txn_id, date, desc, debit, credit, balance = row
    debit_str = f"{debit:.2f}" if debit else ""
    credit_str = f"{credit:.2f}" if credit else ""
    balance_str = f"{balance:.2f}" if balance else "NULL"
    desc_short = (desc[:35] if desc else "")
    print(f'{txn_id:4d} | {str(date):<12} | {desc_short:<35} | {debit_str:>10} | {credit_str:>10} | {balance_str:>12}')

print('-'*80)

# Look for the problem e-transfer entries
print()
print('='*80)
print('LOOKING FOR PROBLEM E-TRANSFER ENTRIES (570.56 amount)')
print('='*80)
print()

cur.execute('''
    SELECT 
        transaction_id,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND transaction_date = '2012-01-03'
    AND (debit_amount = 570.56 OR credit_amount = 570.56)
    ORDER BY transaction_id
''')

etransfer_results = cur.fetchall()
if etransfer_results:
    for row in etransfer_results:
        txn_id, desc, debit, credit, balance = row
        txn_type = "WITHDRAWAL" if debit else "DEPOSIT"
        amount = debit if debit else credit
        print(f'ID {txn_id}: {txn_type:>10} ${amount:>8.2f} | Balance: ${balance:>10.2f} | {desc[:50]}')
else:
    print('NO 570.56 ENTRIES FOUND IN DATABASE FOR JAN 3')

conn.close()

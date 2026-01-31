import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check bank_accounts table
cur.execute('SELECT id, bank_code, account_number, account_holder FROM bank_accounts ORDER BY id')

print('Bank Accounts:')
print('ID | Code | Account Number | Holder')
print('-' * 60)
for row in cur.fetchall():
    print(f'{row[0]} | {row[1]} | {row[2]} | {row[3]}')

print()

# Check 2018 CIBC transactions
cur.execute('''
    SELECT DISTINCT 
        bank_id,
        account_number,
        COUNT(*) as count
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2018
    GROUP BY bank_id, account_number
    ORDER BY bank_id
''')

print('2018 Transactions by Bank Account:')
for bank_id, acct_num, count in cur.fetchall():
    print(f'  Bank ID: {bank_id} | Account: {acct_num} | Count: {count}')

cur.close()
conn.close()

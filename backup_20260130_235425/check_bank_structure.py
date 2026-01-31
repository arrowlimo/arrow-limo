import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check what columns bank_accounts has
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='bank_accounts'
    ORDER BY ordinal_position
""")
print('bank_accounts columns:')
for row in cur.fetchall():
    print(f'  {row[0]}')

print()

# Get all bank_accounts data
cur.execute('SELECT * FROM bank_accounts')
print('bank_accounts data:')
for row in cur.fetchall():
    print(f'  {row}')

print()

# Check 2018 CIBC transactions - which bank_id has account ending in 8362?
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

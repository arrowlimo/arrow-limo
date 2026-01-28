import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# First check what columns exist
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print('banking_transactions columns:', ', '.join(cols))

# Check if there's a bank account column
bank_col = None
for col in cols:
    if 'account' in col.lower():
        bank_col = col
        print(f'\nFound bank account column: {bank_col}')
        break

# Check total banking transactions
cur.execute("SELECT COUNT(*) FROM banking_transactions")
print(f'\nTotal banking transactions: {cur.fetchone()[0]}')

# Look for the $49.05 transaction by amount and date
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions 
    WHERE transaction_date BETWEEN '2012-09-12' AND '2012-09-20' 
    AND (ABS(COALESCE(debit_amount, 0) - 49.05) < 0.01 OR ABS(COALESCE(credit_amount, 0) - 49.05) < 0.01)
    LIMIT 10
""")
rows = cur.fetchall()
print(f'\nMatching $49.05 transactions (09/12-09/20/2012):')
if rows:
    for r in rows:
        print(f'  ID={r[0]}, Date={r[1]}, Desc={r[2][:60]}, Debit={r[3]}, Credit={r[4]}')
else:
    print('  None found')

# Check all Sept 2012 transactions
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions 
    WHERE transaction_date BETWEEN '2012-09-01' AND '2012-09-30'
""")
print(f'\nAll Sept 2012 transactions: {cur.fetchone()[0]}')

cur.close()
conn.close()

import psycopg2, os
conn=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),database='almsdata',user='postgres',password='ArrowLimousine')
cur=conn.cursor()
amount=3293.56

# Exact match
cur.execute('''
select transaction_id, account_number, transaction_date, description, debit_amount, credit_amount 
from banking_transactions 
where (debit_amount=%s or credit_amount=%s) 
order by transaction_date
''', (amount, amount))

rows=cur.fetchall()
print(f'Exact amount match for ${amount}:')
print(f'Found {len(rows)} row(s)')
for r in rows:
    print(f'  TXN {r[0]}: {r[1]} | {r[2]} | {r[3]:<50} | D:{r[4]} C:{r[5]}')

# Close match (within $5)
print(f'\nClose matches (within $5) around 2012-02-14:')
cur.execute('''
select transaction_id, account_number, transaction_date, description, debit_amount, credit_amount 
from banking_transactions 
where transaction_date between date '2012-02-01' and date '2012-02-29'
and (debit_amount between %s and %s or credit_amount between %s and %s)
order by transaction_date, description
''', (amount-5, amount+5, amount-5, amount+5))

rows=cur.fetchall()
print(f'Found {len(rows)} row(s)')
for r in rows:
    print(f'  TXN {r[0]}: {r[1]} | {r[2]} | {r[3]:<50} | D:{r[4]} C:{r[5]}')

# CRA keyword search
print(f'\nCRA-related transactions in Feb 2012:')
cur.execute('''
select transaction_id, account_number, transaction_date, description, debit_amount, credit_amount 
from banking_transactions 
where transaction_date between date '2012-02-01' and date '2012-02-29'
and (description ilike '%CRA%' or description ilike '%CANADA REVENUE%' or description ilike '%REVENUE AGENCY%')
order by transaction_date, description
''')

rows=cur.fetchall()
print(f'Found {len(rows)} row(s)')
for r in rows:
    print(f'  TXN {r[0]}: {r[1]} | {r[2]} | {r[3]:<50} | D:{r[4]} C:{r[5]}')

conn.close()

import psycopg2, os
conn=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),database='almsdata',user='postgres',password='ArrowLimousine')
cur=conn.cursor()

# CRA keyword search full 2012
print('CRA-related transactions in 2012:')
cur.execute('''
select transaction_id, account_number, transaction_date, description, debit_amount, credit_amount 
from banking_transactions 
where transaction_date between date '2012-01-01' and date '2012-12-31'
and (description ilike '%CRA%' or description ilike '%CANADA REVENUE%' or description ilike '%REVENUE AGENCY%' or description ilike '%RECEIVER GENERAL%')
order by transaction_date, description
''')

rows=cur.fetchall()
print(f'Found {len(rows)} row(s)')
for r in rows:
    print(f'  TXN {r[0]}: {r[1]} | {r[2]} | {r[3]:<60} | D:{r[4]} C:{r[5]}')

# Search for NSF or RETURN patterns
print('\n\nNSF/RETURN patterns in Feb-Mar 2012 (bounced cheque timing):')
cur.execute('''
select transaction_id, account_number, transaction_date, description, debit_amount, credit_amount 
from banking_transactions 
where transaction_date between date '2012-02-01' and date '2012-03-31'
and (description ilike '%NSF%' or description ilike '%RETURN%' or description ilike '%BOUNCE%')
order by transaction_date, description
''')

rows=cur.fetchall()
print(f'Found {len(rows)} row(s)')
for r in rows:
    print(f'  TXN {r[0]}: {r[1]} | {r[2]} | {r[3]:<60} | D:{r[4]} C:{r[5]}')

conn.close()

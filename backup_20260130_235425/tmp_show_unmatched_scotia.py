import psycopg2, os
conn=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),database='almsdata',user='postgres',password='ArrowLimousine')
cur=conn.cursor()
cur.execute('''
select r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount 
from receipts r 
where r.business_personal='Business' and r.mapped_bank_account_id=2 
and not exists (select 1 from banking_receipt_matching_ledger bm where bm.receipt_id=r.receipt_id) 
order by r.receipt_date, r.receipt_id
''')
rows=cur.fetchall()
print('Unmatched receipt(s):')
for r in rows:
    print(f'  ID {r[0]}: {r[1]} | {r[2]:<40} | ${r[3]}')
conn.close()

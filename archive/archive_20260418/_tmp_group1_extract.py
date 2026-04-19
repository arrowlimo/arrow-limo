import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

out=Path(r'l:\limo\data\audit\2012_manual_review_group_01.csv')
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gl_account_code, category,
       exclude_from_reports, banking_transaction_id
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND COALESCE(exclude_from_reports,false)=true
ORDER BY receipt_date, receipt_id
LIMIT 20
""")
rows=cur.fetchall()
with out.open('w', newline='', encoding='utf-8') as f:
    w=csv.writer(f)
    w.writerow(['receipt_id','receipt_date','vendor_name','description','gross_amount','gl_account_code','category','exclude_from_reports','banking_transaction_id'])
    for r in rows:
        w.writerow([r['receipt_id'], r['receipt_date'], r['vendor_name'], r['description'], float(r['gross_amount'] or 0), r['gl_account_code'], r['category'], r['exclude_from_reports'], r['banking_transaction_id']])
print('GROUP_FILE:', out)
for r in rows:
    print(f"{r['receipt_id']} | {r['receipt_date']} | {r['vendor_name']} | {float(r['gross_amount'] or 0):.2f} | {r['description']} | GL {r['gl_account_code']} | {r['category']}")
cur.close(); conn.close()

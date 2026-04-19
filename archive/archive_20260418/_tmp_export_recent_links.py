import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

out = Path(r'l:\limo\data\audit\strict_unique_links_recent_20260401.csv')
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, r.banking_transaction_id,
       bt.transaction_date, bt.debit_amount, bt.description
FROM receipts r
JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
WHERE r.updated_at >= NOW() - INTERVAL '15 minutes'
ORDER BY r.updated_at DESC
""")
rows=cur.fetchall()
with out.open('w', newline='', encoding='utf-8') as f:
    w=csv.writer(f)
    w.writerow(['receipt_id','receipt_date','vendor_name','gross_amount','banking_transaction_id','transaction_date','debit_amount','description'])
    for rr in rows:
        w.writerow([rr['receipt_id'], rr['receipt_date'], rr['vendor_name'], rr['gross_amount'], rr['banking_transaction_id'], rr['transaction_date'], rr['debit_amount'], rr['description']])
print('recent_link_audit_rows:', len(rows))
print('recent_link_audit_csv:', out)
cur.close(); conn.close()

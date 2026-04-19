import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

cur.execute("SELECT COUNT(*) cnt, COALESCE(SUM(debit_amount),0) amt FROM banking_transactions WHERE COALESCE(debit_amount,0)>0 AND receipt_id IS NULL")
print('remaining_unlinked_debits:', dict(cur.fetchone()))

cur.execute("""
SELECT COUNT(*) cnt, COALESCE(SUM(amount),0) amt
FROM charter_payments
WHERE charter_id IS NULL AND EXTRACT(YEAR FROM payment_date) IN (2025,2026)
""")
print('remaining_unlinked_charter_2025_2026:', dict(cur.fetchone()))

out = Path(r'l:\limo\data\audit\blank_vendor_token_links_recent_20260401.csv')
cur.execute("""
SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
       bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.description
FROM receipts r
JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
WHERE r.updated_at >= NOW() - INTERVAL '10 minutes'
  AND (bt.vendor_extracted IS NULL OR bt.vendor_extracted='')
ORDER BY r.updated_at DESC
""")
rows = cur.fetchall()
with out.open('w', newline='', encoding='utf-8') as f:
    w=csv.writer(f)
    w.writerow(['receipt_id','receipt_date','vendor_name','gross_amount','transaction_id','transaction_date','debit_amount','description'])
    for rr in rows:
        w.writerow([rr['receipt_id'], rr['receipt_date'], rr['vendor_name'], rr['gross_amount'], rr['transaction_id'], rr['transaction_date'], rr['debit_amount'], rr['description']])
print('blank_vendor_recent_link_rows:', len(rows))
print('blank_vendor_recent_link_csv:', out)

cur.close(); conn.close()

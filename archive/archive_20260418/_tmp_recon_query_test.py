import psycopg2
conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur = conn.cursor()
cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts'""")
cols={r[0] for r in cur.fetchall()}
receipt_total_expr = 'r.gross_amount' if 'gross_amount' in cols else 'r.amount'
if 'gl_account_code' in cols and 'gl_code' in cols:
    receipt_gl_expr='COALESCE(r.gl_account_code, r.gl_code)'
elif 'gl_account_code' in cols:
    receipt_gl_expr='r.gl_account_code'
else:
    receipt_gl_expr='r.gl_code'
q=f"""
SELECT COUNT(*), COALESCE(SUM(COALESCE(bt.debit_amount,0)+COALESCE(bt.credit_amount,0)),0), COALESCE(SUM(COALESCE({receipt_total_expr},0)),0)
FROM banking_transactions bt
LEFT JOIN receipts r ON bt.transaction_id = r.banking_transaction_id
WHERE bt.transaction_date >= %s AND bt.transaction_date <= %s
"""
cur.execute(q, ('2025-01-01','2025-12-31'))
print(cur.fetchone())
cur.close(); conn.close()

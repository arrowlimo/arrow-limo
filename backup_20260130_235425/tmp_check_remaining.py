import psycopg2, os
conn = psycopg2.connect(host=os.environ.get('DB_HOST', 'localhost'), database=os.environ.get('DB_NAME', 'almsdata'), user=os.environ.get('DB_USER', 'postgres'), password=os.environ.get('DB_PASSWORD', 'ArrowLimousine'))
cur = conn.cursor()
cur.execute('''SELECT receipt_id, receipt_date, gross_amount, description FROM receipts WHERE vendor_name ILIKE '%wcb%' AND receipt_date >= '2012-01-01' AND receipt_date <= '2012-09-30' AND banking_transaction_id IS NULL AND gross_amount > 0 ORDER BY gross_amount DESC''')
print('Remaining unlinked WCB invoices:')
for rec_id, rec_date, amount, desc in cur.fetchall():
    amt_f = float(amount)
    desc_str = desc[:30] if desc else "(no desc)"
    print(f'  Receipt {rec_id}: {rec_date} | ${amt_f:>8.2f} | {desc_str}')
cur.close()
conn.close()

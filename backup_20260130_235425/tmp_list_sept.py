import os, psycopg2
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    database=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','ArrowLimousine')
)
cur = conn.cursor()
sql = '''
SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
FROM banking_transactions
WHERE account_number='903990106011'
  AND transaction_date BETWEEN '2012-09-01' AND '2012-09-30'
ORDER BY transaction_date, transaction_id;
'''
cur.execute(sql)
rows = cur.fetchall()
print("Total Sept transactions: {}".format(len(rows)))
for tid, date, desc, d, c, bal in rows:
    d = float(d) if d is not None else 0.0
    c = float(c) if c is not None else 0.0
    bal = float(bal) if bal is not None else 0.0
    print("{} | {:6d} | D {:10.2f} | C {:10.2f} | Bal {:10.2f} | {}".format(date, tid, d, c, bal, desc[:60]))
cur.close(); conn.close()

import psycopg2
from psycopg2.extras import RealDictCursor

check_ids = [77875,60621,102454,102455,78789,100254,82654,100274,82690,60649,100275,82691,60650]

conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute('''
SELECT transaction_id, transaction_date, account_number, description, debit_amount, credit_amount, category, source_file
FROM banking_transactions
WHERE transaction_id = ANY(%s)
ORDER BY transaction_date, transaction_id
''', (check_ids,))
for r in cur.fetchall():
    amt = r['debit_amount'] if r['debit_amount'] is not None else r['credit_amount']
    print(r['transaction_id'], r['transaction_date'], r['account_number'], float(amt or 0), r['description'], '|', r['source_file'])

cur.close(); conn.close()

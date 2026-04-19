import psycopg2
from psycopg2.extras import RealDictCursor

ids = [82544,62569,62579,62666,63005,63036,88735,88765,44961,45269,45191,92932]

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute('''
SELECT transaction_id, transaction_date, description, category, reconciliation_notes, is_nsf_charge
FROM banking_transactions
WHERE transaction_id = ANY(%s)
ORDER BY transaction_date, transaction_id
''', (ids,))
rows = cur.fetchall()
print('candidate_banking_rows', len(rows))
for r in rows:
    print(r['transaction_id'], r['transaction_date'], '| cat=', r['category'], '| nsf=', r['is_nsf_charge'], '| desc=', r['description'])

cur.close(); conn.close()

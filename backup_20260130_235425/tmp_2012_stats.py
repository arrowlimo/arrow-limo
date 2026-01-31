import psycopg2, os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) as cnt, SUM(CASE WHEN parent_receipt_id IS NOT NULL THEN 1 ELSE 0 END) as children, SUM(CASE WHEN is_split_receipt THEN 1 ELSE 0 END) as splits FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2012")
print('2012 Stats:')
r = cur.fetchone()
print(f'  Total receipts: {r[0]}')
print(f'  Children (parent_receipt_id NOT NULL): {r[1]}')
print(f'  Split receipts: {r[2]}')

cur.close()
conn.close()

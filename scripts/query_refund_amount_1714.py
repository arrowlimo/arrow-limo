import os, psycopg2
from datetime import date

DB_HOST=os.environ.get('DB_HOST','localhost')
DB_NAME=os.environ.get('DB_NAME','almsdata')
DB_USER=os.environ.get('DB_USER','postgres')
DB_PASSWORD=os.environ.get('DB_PASSWORD',os.environ.get("DB_PASSWORD"))

conn=psycopg2.connect(host=DB_HOST,dbname=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()
print('--- Refund amount 1714.00 candidates in charter_refunds ---')
cur.execute("""
SELECT id, refund_date, amount, reserve_number, charter_id, description
FROM charter_refunds
WHERE ABS(amount)=1714.00
ORDER BY refund_date DESC
""")
rows=cur.fetchall()
for r in rows:
    print(r)
print(f'Total matches: {len(rows)}')
print('\n--- Rows mentioning 019191 or 019192 in description (regardless of amount) ---')
cur.execute("""
SELECT id, refund_date, amount, reserve_number, charter_id, description
FROM charter_refunds
WHERE (description ILIKE '%019191%' OR description ILIKE '%019192%')
ORDER BY refund_date DESC
""")
rows2=cur.fetchall()
for r in rows2:
    print(r)
print(f'Total desc matches: {len(rows2)}')
print('\n--- Payment rows with amount -1714.00 or 1714.00 ---')
cur.execute("""
SELECT payment_id, payment_date, amount, reserve_number, charter_id, payment_method, notes
FROM payments
WHERE ABS(amount)=1714.00
ORDER BY payment_date DESC
""")
rows3=cur.fetchall()
for r in rows3:
    print(r)
print(f'Total payment matches: {len(rows3)}')
cur.close(); conn.close()

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT id, refund_date, amount, customer, description
    FROM charter_refunds
    WHERE charter_id IS NULL
    AND source_file LIKE 'items-%'
    ORDER BY amount DESC
""")

rows = cur.fetchall()
print(f'Remaining unlinked Square refunds: {len(rows)}\n')
print('ID    | Date       | Amount      | Customer             | Description')
print('-'*100)

for r in rows:
    cust = (r[3] or "")[:20].ljust(20)
    desc = (r[4] or "")[:50]
    print(f'{r[0]:5} | {r[1]} | ${r[2]:>10,.2f} | {cust} | {desc}')

cur.close()
conn.close()

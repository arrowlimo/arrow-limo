import psycopg2

pg = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = pg.cursor()
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_schema='public' AND table_name='charters'
  AND (column_name ILIKE '%total%' OR column_name ILIKE '%balance%' OR column_name ILIKE '%amount%')
ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print('cols', cols)
sel = ', '.join(cols)
cur.execute(f"SELECT {sel} FROM charters WHERE reserve_number='006341'")
row = cur.fetchone()
print('values')
for c,v in zip(cols,row):
    print(c, v)
cur.close(); pg.close()

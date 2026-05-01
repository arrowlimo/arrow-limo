import psycopg2
c = psycopg2.connect(host='localhost', port=5432, database='almsdata', user='postgres', password='ArrowLimousine')
cur = c.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='charters' AND table_schema='public'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(r)
cur.close()
c.close()

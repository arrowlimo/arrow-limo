import psycopg2

conn = psycopg2.connect('host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()

for table in ['charter_charges', 'charters']:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (table,))
    cols = [r[0] for r in cur.fetchall()]
    print(table, cols)

conn.close()

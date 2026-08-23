from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' AND column_name ILIKE '%invoice%' ORDER BY ordinal_position")
print("Invoice cols:", [r[0] for r in cur.fetchall()])
cur.close()
conn.close()

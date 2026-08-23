from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()
cur.execute("SELECT * FROM charters WHERE reserve_number = '020082'")
rows = cur.fetchall()
print(f"Count: {len(rows)}")
for r in rows:
    cur2 = conn.cursor()
    cur2.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
    cols = [c[0] for c in cur2.fetchall()]
    for col, val in zip(cols, r, strict=False):
        if val is not None:
            print(f"  {col}: {val}")
cur.close()
conn.close()

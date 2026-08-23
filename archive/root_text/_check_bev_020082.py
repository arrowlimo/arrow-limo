from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()
cur.execute("SELECT * FROM charter_beverages WHERE charter_id = 19221")
rows = cur.fetchall()
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='charter_beverages' ORDER BY ordinal_position"
)
cols = [c[0] for c in cur.fetchall()]
print("Beverage rows:", len(rows))
for r in rows:
    for col, val in zip(cols, r, strict=False):
        if val is not None:
            print(f"  {col}: {val}")
    print("---")
conn.close()

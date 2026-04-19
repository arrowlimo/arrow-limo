import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

tables = ["charters", "charter_charges", "charter_payments", "drivers", "vehicles", "clients", "charge_catalog", "employees"]
for t in tables:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (t,))
    cols = cur.fetchall()
    print(f"\n--- {t} ---")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")

conn.close()

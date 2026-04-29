import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

for tbl in ['employees', 'payroll_entries', 'vendor_accounts', 'banking_transactions', 'receipts']:
    cur.execute("""SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (tbl,))
    rows = cur.fetchall()
    print(f"\n=== {tbl} ({len(rows)} cols) ===")
    for r in rows: print(f"  {r[0]}  ({r[1]})")

# Check if t4_data or similar tables exist
cur.execute("""SELECT table_name FROM information_schema.tables
    WHERE table_schema='public' AND table_name ILIKE '%t4%' OR table_name ILIKE '%payroll%'""")
print("\n=== T4/payroll tables ===")
for r in cur.fetchall(): print(f"  {r[0]}")

# Check GL account types present
cur.execute("""SELECT DISTINCT account_type, COUNT(*) FROM general_ledger 
    WHERE account_type IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20""")
print("\n=== GL account_type values ===")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")

# Check fiscal years available
cur.execute("SELECT DISTINCT EXTRACT(YEAR FROM date)::int as yr FROM general_ledger WHERE date IS NOT NULL ORDER BY 1")
print("\n=== GL years ===")
for r in cur.fetchall(): print(f"  {r[0]}")

cur.close(); conn.close()

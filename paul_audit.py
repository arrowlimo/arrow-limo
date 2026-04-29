import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, database="almsdata", user="postgres", password="ArrowLimousine")
conn.set_session(readonly=True)
cur = conn.cursor()

# Step 1: employees columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print("EMPLOYEES COLUMNS:", cols)

# Step 2: Find Paul Richard in employees
select_cols = list(dict.fromkeys(
    ["employee_id"] +
    [c for c in cols if c in ["employee_number","first_name","last_name","full_name","name"]] +
    [c for c in cols if "sin" in c.lower() or "social" in c.lower() or "insurance" in c.lower()]
))
select_cols = [c for c in select_cols if c in cols]
print("SELECTING:", select_cols)

try:
    q = "SELECT " + ",".join(select_cols) + " FROM employees WHERE LOWER(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) LIKE '%paul%richard%' OR LOWER(COALESCE(last_name,'')) LIKE '%richard%'"
    cur.execute(q)
    rows = cur.fetchall()
    print("PAUL EMPLOYEE ROWS:")
    for r in rows:
        print(dict(zip(select_cols, r)))
except Exception as e:
    print("ERR employees query:", e)
    conn.rollback()
    cur2 = conn.cursor()
    cur2.execute("SELECT * FROM employees WHERE LOWER(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) LIKE '%paul%richard%'")
    rows = cur2.fetchall()
    print("RAW PAUL ROWS:", rows)

# Step 3: Find T4-related tables
cur3 = conn.cursor()
cur3.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE 't4%' OR table_name LIKE '%t4%') ORDER BY table_name")
t4_tables = [r[0] for r in cur3.fetchall()]
print("T4 TABLES:", t4_tables)

# Step 4: Find payroll-related tables
cur3.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (
    table_name LIKE '%payroll%' OR table_name LIKE '%pay_master%' OR table_name LIKE '%pay_entri%'
    OR table_name LIKE '%compensation%' OR table_name LIKE '%earnings%' OR table_name LIKE '%wages%'
    OR table_name LIKE '%income%'
) ORDER BY table_name""")
pay_tables = [r[0] for r in cur3.fetchall()]
print("PAYROLL TABLES:", pay_tables)

cur.close()
conn.close()

import psycopg2

conn = psycopg2.connect(dbname="almsdata", host="localhost")
cur = conn.cursor()

# ============================================================
# 1. EMPLOYEES TABLE
# ============================================================
print("=== 1. EMPLOYEE TABLE COLUMNS ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employees' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print("employees columns:", cols)

name_cols = [c for c in cols if any(x in c.lower() for x in ["name","first","last","full"])]
sin_cols  = [c for c in cols if any(x in c.lower() for x in ["sin","social","insurance","ssn"])]
num_cols  = [c for c in cols if any(x in c.lower() for x in ["employee_id","employee_number","emp_id","emp_num"])]
print("name cols:", name_cols, "| sin cols:", sin_cols, "| id/num cols:", num_cols)

# Build a WHERE clause searching all name-like columns for Paul Richard
if name_cols:
    where_parts = []
    for c in name_cols:
        where_parts.append("LOWER({}) LIKE '%paul%richard%'".format(c))
        where_parts.append("(LOWER({}) LIKE '%paul%' AND LOWER({}) LIKE '%richard%')".format(c, c))
    # Also try first+last combo
    if len(name_cols) >= 2:
        for i in range(len(name_cols)):
            for j in range(len(name_cols)):
                if i != j:
                    where_parts.append("(LOWER({}) LIKE '%paul%' AND LOWER({}) LIKE '%richard%')".format(name_cols[i], name_cols[j]))
    where = " OR ".join(set(where_parts))
    sel_cols = list(dict.fromkeys(num_cols + name_cols + sin_cols + ["employee_id"] if "employee_id" in cols else num_cols + name_cols + sin_cols))
    # fallback: just grab all cols
    sel = ", ".join(cols[:20])
    q = "SELECT {} FROM employees WHERE {}".format(sel, where)
    print("\nEmployee search query:", q)
    cur.execute(q)
    rows = cur.fetchall()
    print("Rows found:", len(rows))
    for r in rows:
        print(r)
else:
    # No name columns found - just dump first 5 rows
    cur.execute("SELECT * FROM employees LIMIT 5")
    print("Sample rows:", cur.fetchall())

# ============================================================
# 2. T4 TABLES
# ============================================================
print("\n=== 2. T4 TABLES ===")
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 't4%' ORDER BY table_name")
t4_tables = [r[0] for r in cur.fetchall()]
print("T4 tables:", t4_tables)

# ============================================================
# 3. PAYROLL TABLES
# ============================================================
print("\n=== 3. PAYROLL TABLES (checking existence) ===")
payroll_candidates = [
    "employee_pay_master","driver_payroll","employee_monthly_compensation",
    "employee_annual_compensation","employee_pay_entries"
]
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
all_tables = [r[0] for r in cur.fetchall()]
existing_payroll = [t for t in payroll_candidates if t in all_tables]
print("Candidate payroll tables found:", existing_payroll)

# Also show any table with payroll/pay/compensation/wage in name
pay_related = [t for t in all_tables if any(x in t.lower() for x in ["payroll","pay_","compensation","wage","salary","t4","earning","deduct"])]
print("All pay-related tables in schema:", pay_related)

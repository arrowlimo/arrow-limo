import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
conn.set_session(readonly=True)
cur = conn.cursor()

# Q1
print("=== Q1: employees WHERE employee_id=10 ===")
cols = "employee_id, employee_number, full_name, salary, salary_deferred, hourly_rate, hourly_pay_rate"
try:
    cur.execute(f"SELECT {cols} FROM employees WHERE employee_id = 10")
    rows = cur.fetchall()
    print(" | ".join(d[0] for d in cur.description))
    print("-"*80)
    for r in rows: print(" | ".join(str(v) for v in r))
except Exception as e:
    print("Error:", e); conn.rollback()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employees' ORDER BY ordinal_position")
    print("Available columns:", [r[0] for r in cur.fetchall()])

# Q2
print("\n=== Q2: t4_compliance_corrections employee_id=10, year>=2012 ===")
cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='t4_compliance_corrections')")
if not cur.fetchone()[0]:
    print("Table does NOT exist.")
else:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='t4_compliance_corrections' ORDER BY ordinal_position")
    all_cols=[r[0] for r in cur.fetchall()]
    print("Columns:", all_cols)
    want=["employee_id","year","status","reason","notes"]
    inc=[c for c in all_cols if any(k in c.lower() for k in ["income","amount","gross","net","box","wage","earn","pay","t4"])]
    keep=[c for c in all_cols if c in want or c in inc]
    if not keep: keep=all_cols
    cur.execute("SELECT " + ", ".join(keep) + " FROM t4_compliance_corrections WHERE employee_id=10 AND year>=2012 ORDER BY year")
    rows=cur.fetchall()
    print(" | ".join(d[0] for d in cur.description)); print("-"*80)
    for r in rows: print(" | ".join(str(v) for v in r))
    if not rows: print("(no rows)")

# Q3
print("\n=== Q3: employee_t4_summary employee_id=10, year IN (2013,2014) ===")
cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='employee_t4_summary')")
if not cur.fetchone()[0]:
    print("Table does NOT exist.")
else:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employee_t4_summary' ORDER BY ordinal_position")
    all_cols=[r[0] for r in cur.fetchall()]
    print("Columns:", all_cols)
    amt=[c for c in all_cols if any(k in c.lower() for k in ["amount","income","gross","net","box","wage","earn","pay","salary","total","cpp","ei","tax","fed","prov","pension","benefit"])]
    id_=[c for c in all_cols if c in ("employee_id","year","tax_year","full_name","employee_number")]
    keep=id_+[c for c in amt if c not in id_]
    if not keep: keep=all_cols
    sel=", ".join(keep)
    cur.execute("SELECT " + sel + " FROM employee_t4_summary WHERE employee_id=10 AND year IN (2013,2014) ORDER BY year")
    rows=cur.fetchall()
    print(" | ".join(d[0] for d in cur.description)); print("-"*80)
    for r in rows: print(" | ".join(str(v) for v in r))
    if not rows:
        print("(no rows for year col, trying tax_year...)")
        try:
            cur.execute("SELECT " + sel + " FROM employee_t4_summary WHERE employee_id=10 AND tax_year IN (2013,2014) ORDER BY tax_year")
            rows2=cur.fetchall()
            print(" | ".join(d[0] for d in cur.description)); print("-"*80)
            for r in rows2: print(" | ".join(str(v) for v in r))
            if not rows2: print("(still no rows)")
        except Exception as e2: print("tax_year err:", e2)

conn.close()

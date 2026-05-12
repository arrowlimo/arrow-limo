import os
import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, database="almsdata", user="postgres", password=os.getenv("ALMS_DB_PASSWORD", ""))
conn.set_session(readonly=True)

PAUL_ID = 10
PAUL_SIN = "637660614"

def run(sql, params=None):
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return cols, rows
    except Exception as e:
        conn.rollback()
        return None, str(e)

# ---- T4 TABLES ----
# employee_t4_records columns
cols, rows = run("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employee_t4_records' ORDER BY ordinal_position")
t4r_cols = [r[0] for r in rows]
print("employee_t4_records COLS:", t4r_cols)

cols, rows = run("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employee_t4_summary' ORDER BY ordinal_position")
t4s_cols = [r[0] for r in rows]
print("employee_t4_summary COLS:", t4s_cols)

# Query employee_t4_records for Paul by employee_id
cols, rows = run("SELECT * FROM employee_t4_records WHERE employee_id=%s AND tax_year >= 2012 ORDER BY tax_year", (PAUL_ID,))
if cols is None:
    print("employee_t4_records by emp_id err:", rows)
    cols, rows = run("SELECT * FROM employee_t4_records WHERE sin=%s AND tax_year >= 2012 ORDER BY tax_year", (PAUL_SIN,))
    if cols is None:
        print("employee_t4_records by SIN err:", rows)
    else:
        print("T4 RECORDS (by SIN):")
        for r in rows: print(dict(zip(cols, r)))
else:
    print("T4 RECORDS (by emp_id):")
    for r in rows: print(dict(zip(cols, r)))

# Query employee_t4_summary for Paul
cols, rows = run("SELECT * FROM employee_t4_summary WHERE employee_id=%s AND tax_year >= 2012 ORDER BY tax_year", (PAUL_ID,))
if cols is None:
    print("employee_t4_summary err:", rows)
else:
    print("T4 SUMMARY (by emp_id):")
    for r in rows: print(dict(zip(cols, r)))

# ---- PAYROLL TABLES ----
# employee_pay_master columns
cols, rows = run("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employee_pay_master' ORDER BY ordinal_position")
epm_cols = [r[0] for r in rows] if cols else []
print("employee_pay_master COLS:", epm_cols)

# employee_pay_master for Paul
cols, rows = run("SELECT * FROM employee_pay_master WHERE employee_id=%s AND EXTRACT(year FROM pay_date) >= 2012 ORDER BY pay_date", (PAUL_ID,))
if cols is None:
    print("employee_pay_master err:", rows)
    # try year column
    cols, rows = run("SELECT * FROM employee_pay_master WHERE employee_id=%s ORDER BY 1 LIMIT 5", (PAUL_ID,))
    print("EPM sample:", cols, rows[:3] if rows else [])
else:
    print("EMPLOYEE_PAY_MASTER rows:", len(rows))
    # summarize by year
    year_sums = {}
    for r in rows:
        d = dict(zip(cols, r))
        yr = None
        for k in ["pay_date","period_end","date","year","tax_year"]:
            if k in d and d[k]:
                try:
                    yr = int(str(d[k])[:4])
                    break
                except: pass
        if yr is None: yr = "?"
        if yr not in year_sums: year_sums[yr] = {"count":0, "gross":0, "net":0}
        year_sums[yr]["count"] += 1
        for gk in ["gross_pay","gross_earnings","gross","total_gross","employment_income"]:
            if gk in d and d[gk]: 
                try: year_sums[yr]["gross"] += float(d[gk])
                except: pass
        for nk in ["net_pay","net","total_net"]:
            if nk in d and d[nk]:
                try: year_sums[yr]["net"] += float(d[nk])
                except: pass
    print("EPM YEAR SUMMARY:")
    for yr in sorted(year_sums): print(f"  {yr}: {year_sums[yr]}")

# driver_payroll
cols, rows = run("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='driver_payroll' ORDER BY ordinal_position")
dp_cols = [r[0] for r in rows] if cols else []
print("driver_payroll COLS:", dp_cols)

cols, rows = run("SELECT * FROM driver_payroll WHERE employee_id=%s ORDER BY 1", (PAUL_ID,))
if cols is None:
    print("driver_payroll err:", rows)
    cols, rows = run("SELECT * FROM driver_payroll WHERE driver_id=%s ORDER BY 1", (PAUL_ID,))
    if cols is None: print("driver_payroll driver_id err:", rows)
    else:
        print("DRIVER_PAYROLL by driver_id rows:", len(rows))
        for r in rows[:5]: print(dict(zip(cols,r)))
else:
    print("DRIVER_PAYROLL rows:", len(rows))
    for r in rows[:10]: print(dict(zip(cols,r)))

# employee_pay_entries
cols, rows = run("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='employee_pay_entries' ORDER BY ordinal_position")
epe_cols = [r[0] for r in rows] if cols else []
print("employee_pay_entries COLS:", epe_cols)

cols, rows = run("SELECT * FROM employee_pay_entries WHERE employee_id=%s AND EXTRACT(year FROM entry_date) >= 2012 ORDER BY entry_date", (PAUL_ID,))
if cols is None:
    print("employee_pay_entries err:", rows)
    # try without date filter
    cols, rows = run("SELECT * FROM employee_pay_entries WHERE employee_id=%s ORDER BY 1 LIMIT 10", (PAUL_ID,))
    if cols is None: print("employee_pay_entries simple err:", rows)
    else:
        print("EPE sample:", len(rows))
        for r in rows[:5]: print(dict(zip(cols,r)))
else:
    print("EMPLOYEE_PAY_ENTRIES rows:", len(rows))
    year_sums2 = {}
    for r in rows:
        d = dict(zip(cols,r))
        yr = None
        for k in ["entry_date","pay_date","date","year"]:
            if k in d and d[k]:
                try: yr = int(str(d[k])[:4]); break
                except: pass
        if yr is None: yr = "?"
        if yr not in year_sums2: year_sums2[yr] = {"count":0,"gross":0}
        year_sums2[yr]["count"] += 1
        for gk in ["gross","gross_pay","amount","employment_income","earnings"]:
            if gk in d and d[gk]:
                try: year_sums2[yr]["gross"] += float(d[gk])
                except: pass
    print("EPE YEAR SUMMARY:")
    for yr in sorted(year_sums2): print(f"  {yr}: {year_sums2[yr]}")

conn.close()
print("DONE")

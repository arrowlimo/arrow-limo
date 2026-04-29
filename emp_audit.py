import re
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect("host=localhost dbname=almsdata user=postgres password=ArrowLimousine")

with conn.cursor(row_factory=dict_row) as cur:
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='employees'
        ORDER BY ordinal_position
    """)
    emp_cols = [r['column_name'] for r in cur.fetchall()]

    if 'employee_id' not in emp_cols or 'employee_number' not in emp_cols:
        raise RuntimeError(f"employees table missing required columns. found={emp_cols}")

    if 'full_name' in emp_cols:
        name_expr = "COALESCE(full_name, '')"
    elif 'first_name' in emp_cols and 'last_name' in emp_cols:
        name_expr = "TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))"
    else:
        name_expr = "''"

    cur.execute(f"""
        SELECT employee_id, {name_expr} AS full_name, COALESCE(employee_number,'') AS employee_number
        FROM public.employees
        ORDER BY employee_id
    """)
    rows = cur.fetchall()

patterns = {
    'valid_d': re.compile(r'^D\d{3}$'),
    'valid_h': re.compile(r'^H\d{3}$'),
    'valid_o': re.compile(r'^O\d{3}$'),
    'legacy_dr': re.compile(r'^DR\d{1,3}$'),
}

buckets = {k: 0 for k in ['valid_d','valid_h','valid_o','legacy_dr','other']}
other_rows, legacy_rows = [], []

for r in rows:
    n = r['employee_number'] or ''
    hit = None
    for k, p in patterns.items():
        if p.match(n):
            hit = k
            break
    if hit is None:
        buckets['other'] += 1
        other_rows.append(r)
    else:
        buckets[hit] += 1
        if hit == 'legacy_dr':
            legacy_rows.append(r)

print('EMPLOYEE_NUMBER AUDIT')
print(f"total_employees: {len(rows)}")
print("bucket_counts: " + ", ".join(f"{k}={buckets[k]}" for k in ['valid_d','valid_h','valid_o','legacy_dr','other']))

print("\nother_rows (employee_id, full_name, employee_number):")
if other_rows:
    for r in other_rows:
        print(f"{r['employee_id']}\t{r['full_name']}\t{r['employee_number']}")
else:
    print('(none)')

print("\nlegacy_dr sample (up to 20):")
if legacy_rows:
    for r in legacy_rows[:20]:
        print(f"{r['employee_id']}\t{r['full_name']}\t{r['employee_number']}")
else:
    print('(none)')

with conn.cursor(row_factory=dict_row) as cur:
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='driver_employee_mapping'
        ORDER BY ordinal_position
    """)
    map_cols = cur.fetchall()

print("\npublic.driver_employee_mapping columns:")
if map_cols:
    for c in map_cols:
        print(f"{c['column_name']} ({c['data_type']})")
else:
    print('(table missing or no columns)')

print("\ndriver_employee_mapping joined sample (up to 20 rows):")
if map_cols:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT m.*, e.employee_id AS e_employee_id,
                   CASE
                     WHEN EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='employees' AND column_name='full_name'
                     ) THEN e.full_name
                     WHEN EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='employees' AND column_name='first_name'
                     )
                      AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='employees' AND column_name='last_name'
                     ) THEN TRIM(COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,''))
                     ELSE NULL
                   END AS full_name,
                   e.employee_number
            FROM public.driver_employee_mapping m
            LEFT JOIN public.employees e ON e.employee_id = m.employee_id
            ORDER BY m.employee_id NULLS LAST
            LIMIT 20
        """)
        sample = cur.fetchall()
    if sample:
        keys = list(sample[0].keys())
        print("\t".join(keys))
        for r in sample:
            print("\t".join('' if r[k] is None else str(r[k]) for k in keys))
    else:
        print('(no rows)')
else:
    print('(skipped)')

conn.close()

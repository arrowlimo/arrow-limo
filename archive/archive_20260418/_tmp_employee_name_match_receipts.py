import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Discover employee source table(s)
cur.execute(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='public' AND table_name ILIKE '%employee%'
    ORDER BY table_name
    """
)
employee_tables = [r['table_name'] for r in cur.fetchall()]
print("employee_tables:")
for t in employee_tables:
    print(" -", t)

# Try common employee table/columns patterns
name_rows = []
patterns = [
    ("employees", "SELECT employee_id, first_name, last_name, status FROM employees"),
    ("employee", "SELECT employee_id, first_name, last_name, status FROM employee"),
    ("employees", "SELECT employee_id, employee_name FROM employees"),
    ("employee", "SELECT employee_id, employee_name FROM employee"),
]

for label, sql in patterns:
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        if rows:
            name_rows = rows
            print(f"\nusing_source: {label} ({len(rows)} rows)")
            break
    except Exception:
        continue

if not name_rows:
    print("\nNo readable employee name source found with common patterns.")
    conn.close()
    raise SystemExit(0)

# Build normalized name tokens
employees = []
for r in name_rows:
    first = (r.get('first_name') or '').strip()
    last = (r.get('last_name') or '').strip()
    if not first and not last and r.get('employee_name'):
        parts = str(r['employee_name']).strip().split()
        first = parts[0] if parts else ''
        last = parts[-1] if len(parts) > 1 else ''
    full = f"{first} {last}".strip()
    if full:
        employees.append((first, last, full))

# De-duplicate names
seen = set()
unique_employees = []
for first, last, full in employees:
    key = full.lower()
    if key not in seen:
        seen.add(key)
        unique_employees.append((first, last, full))

print(f"employee_name_count: {len(unique_employees)}")

# Name-based matching against receipts.vendor_name and receipts.description
matched_ids = set()
for first, last, full in unique_employees:
    terms = [full]
    if first and last:
        terms.append(f"{last}, {first}")
        terms.append(f"{first} {last[0]}")

    for term in terms:
        cur.execute(
            """
            SELECT receipt_id
            FROM receipts
            WHERE COALESCE(vendor_name, '') ILIKE %s
               OR COALESCE(description, '') ILIKE %s
            """,
            (f"%{term}%", f"%{term}%")
        )
        for rr in cur.fetchall():
            matched_ids.add(rr['receipt_id'])

print(f"matched_receipt_count: {len(matched_ids)}")

if matched_ids:
    cur.execute(
        """
        SELECT COALESCE(SUM(gross_amount), 0) AS amt
        FROM receipts
        WHERE receipt_id = ANY(%s)
        """,
        (list(matched_ids),)
    )
    total_amt = cur.fetchone()['amt']
    print(f"matched_receipt_amount: {float(total_amt):.2f}")

    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gl_code, gl_account_code
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY gross_amount DESC NULLS LAST
        LIMIT 40
        """,
        (list(matched_ids),)
    )
    print("\nTop matched receipts:")
    for r in cur.fetchall():
        print(
            r['receipt_id'],
            r['receipt_date'],
            r['vendor_name'],
            r['description'],
            float(r['gross_amount'] or 0),
            r['gl_code'],
            r['gl_account_code'],
        )

conn.close()

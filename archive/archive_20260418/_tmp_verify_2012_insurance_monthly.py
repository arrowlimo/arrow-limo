import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    """
    SELECT vendor_name, invoice_date, invoice_amount, invoice_number, notes, vendor_invoice_id
    FROM vendor_invoices
    WHERE invoice_date >= DATE '2012-01-01'
      AND invoice_date < DATE '2013-01-01'
      AND (
        vendor_name ILIKE '%insurance%'
        OR notes ILIKE '%insurance%'
      )
    ORDER BY vendor_name, invoice_date, vendor_invoice_id
    """
)
rows = cur.fetchall()

companies = defaultdict(list)
for r in rows:
    companies[(r['vendor_name'] or 'UNKNOWN').strip()].append(r)

print(f"Insurance-related invoice rows in 2012: {len(rows)}")
print(f"Insurance companies found: {len(companies)}\n")

if not companies:
    print("No insurance companies found in vendor_invoices for 2012.")
    conn.close()
    raise SystemExit(0)

for company in sorted(companies.keys()):
    monthly = defaultdict(float)
    monthly_count = defaultdict(int)
    total = 0.0

    for r in companies[company]:
        m = r['invoice_date'].month
        amt = float(r['invoice_amount'] or 0)
        monthly[m] += amt
        monthly_count[m] += 1
        total += amt

    missing = [m for m in range(1, 13) if monthly_count[m] == 0]

    print(f"=== {company} ===")
    print(f"Rows: {len(companies[company])} | Total: ${total:,.2f}")
    for m in range(1, 13):
        print(f"  {m:02d}: count={monthly_count[m]}, amount=${monthly[m]:,.2f}")
    if missing:
        print("Missing months:", ", ".join(f"{m:02d}" for m in missing))
    else:
        print("Missing months: none (all 12 months present)")
    print()

print("Detail rows:\n")
for r in rows:
    print(
        f"{r['vendor_name']} | {r['invoice_date']} | {r['invoice_number']} | ${float(r['invoice_amount'] or 0):,.2f} | {r['notes']}"
    )

conn.close()

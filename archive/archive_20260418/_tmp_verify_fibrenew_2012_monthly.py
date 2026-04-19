import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    """
    SELECT vendor_invoice_id, vendor_name, invoice_number, invoice_date, invoice_amount, status, notes
    FROM vendor_invoices
    WHERE invoice_date >= DATE '2012-01-01'
      AND invoice_date < DATE '2013-01-01'
      AND vendor_name ILIKE '%fibrenew%'
    ORDER BY invoice_date, vendor_invoice_id
    """
)
rows = cur.fetchall()

print(f"Fibrenew invoices in 2012 (all): {len(rows)}")

# Utility detection heuristic for this table
# Exclude rows where notes or invoice number clearly indicate utilities.
def is_utility(r):
    inv = (r['invoice_number'] or '').lower()
    notes = (r['notes'] or '').lower()
    return ('util' in inv) or ('utilit' in notes) or ('utility' in notes)

monthly_all = defaultdict(float)
monthly_non_util = defaultdict(float)
monthly_non_util_count = defaultdict(int)

for r in rows:
    m = r['invoice_date'].month
    amt = float(r['invoice_amount'] or 0)
    monthly_all[m] += amt
    if not is_utility(r):
        monthly_non_util[m] += amt
        monthly_non_util_count[m] += 1

print("\nMonthly coverage (non-utility Fibrenew invoices):")
missing = []
for m in range(1, 13):
    cnt = monthly_non_util_count[m]
    amt = monthly_non_util[m]
    if cnt == 0:
        missing.append(m)
    print(f"  {m:02d}: count={cnt}, amount=${amt:,.2f}")

print("\nTotals:")
print(f"  All Fibrenew 2012 invoiced: ${sum(monthly_all.values()):,.2f}")
print(f"  Non-utility 2012 invoiced: ${sum(monthly_non_util.values()):,.2f}")

if missing:
    print("\nMissing non-utility months:", ", ".join(f"{m:02d}" for m in missing))
else:
    print("\nAll 12 months have non-utility Fibrenew invoices.")

print("\nDetail rows:")
for r in rows:
    util_flag = "UTILITY" if is_utility(r) else "NON_UTILITY"
    print(
        f"{r['invoice_date']} | {r['invoice_number']} | ${float(r['invoice_amount'] or 0):,.2f} | {util_flag} | {r['status']} | {r['notes']}"
    )

conn.close()

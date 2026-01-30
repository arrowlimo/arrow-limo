"""
Report 2012 charter runs with outstanding balances.

Criteria:
- charter_date between 2012-01-01 and 2012-12-31 inclusive
- balance > 0.01 (avoid rounding noise)
- exclude cancelled charters if a cancelled flag/column exists (cancelled, status)
- show total count, total outstanding, average balance
- list top 25 by balance
- provide per-month summary
"""
import psycopg2
from decimal import Decimal

THRESHOLD = Decimal('0.01')

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

print("="*80)
print("2012 CHARTERS WITH OUTSTANDING BALANCES")
print("="*80)

conn = get_conn()
cur = conn.cursor()

# Detect cancellation column presence
cur.execute("""
SELECT column_name FROM information_schema.columns
WHERE table_name='charters'
""")
cols = {r[0] for r in cur.fetchall()}

cancel_filter = ""  # dynamic
if 'cancelled' in cols:
    cancel_filter = "AND (cancelled IS NULL OR cancelled = FALSE)"
elif 'status' in cols:
    # assume statuses like 'Cancelled'
    cancel_filter = "AND (status IS NULL OR status NOT ILIKE 'cancel%')"

query = f"""
SELECT charter_id, reserve_number, client_id, charter_date, balance, paid_amount, total_amount_due
FROM charters
WHERE charter_date >= DATE '2012-01-01'
  AND charter_date < DATE '2013-01-01'
  AND balance > %s
  {cancel_filter}
ORDER BY balance DESC
"""
cur.execute(query, (THRESHOLD,))
rows = cur.fetchall()

count = len(rows)
if count == 0:
    print("No 2012 charters with outstanding balance above threshold.")
else:
    total_outstanding = sum((r[4] or 0) for r in rows)
    avg_balance = (total_outstanding / count) if count else 0
    print(f"Outstanding charters: {count}")
    print(f"Total outstanding: ${total_outstanding:,.2f}")
    print(f"Average balance: ${avg_balance:,.2f}")

    # Monthly breakdown
    cur.execute(f"""
    SELECT DATE_TRUNC('month', charter_date)::date AS month,
           COUNT(*) AS cnt,
           SUM(balance) AS sum_bal,
           AVG(balance) AS avg_bal
    FROM charters
    WHERE charter_date >= DATE '2012-01-01'
      AND charter_date < DATE '2013-01-01'
      AND balance > %s
      {cancel_filter}
    GROUP BY 1
    ORDER BY 1
    """, (THRESHOLD,))
    month_rows = cur.fetchall()

    print("\nPer-month summary (month | count | total | avg):")
    for m in month_rows:
        month, cnt, sum_bal, avg_bal_m = m
        print(f"{month} | {cnt:3d} | ${sum_bal:10,.2f} | ${avg_bal_m:8,.2f}")

    # Top 25
    print("\nTop 25 balances:")
    print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<10} {'Balance':>12} {'Paid':>12} {'TotalDue':>12}")
    print('-'*70)
    for r in rows[:25]:
        charter_id, reserve_number, client_id, charter_date, balance, paid_amount, total_due = r
        print(f"{charter_id:<10} {str(reserve_number or ''):<8} {charter_date} ${balance:11,.2f} ${(paid_amount or 0):11,.2f} ${(total_due or 0):11,.2f}")

cur.close(); conn.close()
print("\n" + "="*80)
print("REPORT COMPLETE")
print("="*80)

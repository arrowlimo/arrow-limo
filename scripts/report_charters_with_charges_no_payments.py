"""
List charters (all years by default) that have charges but no payments and are not cancelled.

Definition:
- Not cancelled (cancel filter via columns: cancelled/status)
- Charges exist: total_amount_due > 0 OR balance > 0
- No payments: COALESCE(paid_amount,0) = 0
- Useful fields: charter_id, reserve_number, date, client_id, total_amount_due, paid_amount, balance, status
- Options: optional year filter via --year YYYY
"""
import argparse
import psycopg2


def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )


def get_cancel_filter(cur):
    cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='charters'
    """)
    cols = {r[0] for r in cur.fetchall()}
    if 'cancelled' in cols:
        return "AND (cancelled IS NULL OR cancelled = FALSE)"
    if 'status' in cols:
        return "AND (status IS NULL OR status NOT ILIKE 'cancel%')"
    return ""


parser = argparse.ArgumentParser(description='Report charters with charges but no payments (not cancelled).')
parser.add_argument('--year', type=int, help='Filter by calendar year (YYYY)')
args = parser.parse_args()

conn = get_conn()
cur = conn.cursor()

cancel_filter = get_cancel_filter(cur)

year_clause = ""
params = []
if args.year:
    year_clause = "AND charter_date >= %s AND charter_date < %s"
    params.extend([f"{args.year}-01-01", f"{args.year+1}-01-01"])

# Prepare query: no payments and positive charges
query = f"""
SELECT charter_id, reserve_number, charter_date, client_id,
       COALESCE(total_amount_due, 0) as total_due,
       COALESCE(paid_amount, 0) as paid,
       COALESCE(balance, 0) as balance,
       status
FROM charters
WHERE 1=1
  {year_clause}
  {cancel_filter}
  AND COALESCE(paid_amount, 0) = 0
  AND (COALESCE(total_amount_due, 0) > 0 OR COALESCE(balance, 0) > 0)
ORDER BY charter_date ASC, charter_id ASC
"""

cur.execute(query, params)
rows = cur.fetchall()

print("="*100)
print("CHARTERS WITH CHARGES BUT NO PAYMENTS (NOT CANCELLED)")
print("="*100)

if args.year:
    print(f"Year filter: {args.year}")

count = len(rows)
print(f"Total runs: {count}")

if count:
    total_due = sum(float(r[4]) for r in rows)
    total_balance = sum(float(r[6]) for r in rows)
    print(f"Total charges (sum total_due): ${total_due:,.2f}")
    print(f"Total outstanding (sum balance): ${total_balance:,.2f}")

    # Monthly distribution
    cur.execute(f"""
        SELECT DATE_TRUNC('month', charter_date)::date as month,
               COUNT(*) as cnt,
               SUM(COALESCE(total_amount_due, 0)) as sum_due,
               SUM(COALESCE(balance, 0)) as sum_bal
        FROM charters
        WHERE 1=1
          {year_clause}
          {cancel_filter}
          AND COALESCE(paid_amount, 0) = 0
          AND (COALESCE(total_amount_due, 0) > 0 OR COALESCE(balance, 0) > 0)
        GROUP BY 1
        ORDER BY 1
    """, params)
    months = cur.fetchall()

    print("\nMonthly breakdown (month | runs | charges | outstanding):")
    for m in months:
        month, cnt, sum_due, sum_bal = m
        print(f"{month} | {cnt:4d} | ${float(sum_due or 0):10,.2f} | ${float(sum_bal or 0):10,.2f}")

    # Show first 25 rows
    print("\nFirst 25 runs:")
    print(f"{'CharterID':<10} {'Reserve':<8} {'Date':<10} {'Client':<8} {'TotalDue':>12} {'Paid':>10} {'Balance':>12} {'Status':<12}")
    print("-"*100)
    for r in rows[:25]:
        charter_id, reserve, cdate, client, due, paid, bal, status = r
        print(f"{charter_id:<10} {str(reserve or ''):<8} {cdate} {str(client or ''):<8} ${float(due):11,.2f} ${float(paid):9,.2f} ${float(bal):11,.2f} {str(status or ''):<12}")

cur.close(); conn.close()

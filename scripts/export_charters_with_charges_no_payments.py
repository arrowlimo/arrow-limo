"""
Export charters (all years or a specific year) that have charges but no payments and are not cancelled to CSV.

Definition:
- Not cancelled (cancel filter via columns: cancelled/status)
- Charges exist: total_amount_due > 0 OR balance > 0
- No payments: COALESCE(paid_amount,0) = 0
- Output CSV columns: charter_id,reserve_number,charter_date,client_id,total_amount_due,paid_amount,balance,status
- Options: --year YYYY, --out path (default: reports/charters_no_payments_all.csv)
"""
import argparse
import csv
import os
import psycopg2


def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
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


parser = argparse.ArgumentParser(description='Export charters with charges but no payments (not cancelled) to CSV.')
parser.add_argument('--year', type=int, help='Filter by calendar year (YYYY)')
parser.add_argument('--out', type=str, default='L:\\limo\\reports\\charters_no_payments_all.csv', help='Output CSV file path')
args = parser.parse_args()

conn = get_conn()
cur = conn.cursor()

cancel_filter = get_cancel_filter(cur)

year_clause = ""
params = []
if args.year:
    year_clause = "AND charter_date >= %s AND charter_date < %s"
    params.extend([f"{args.year}-01-01", f"{args.year+1}-01-01"])

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

os.makedirs(os.path.dirname(args.out), exist_ok=True)

with open(args.out, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['charter_id','reserve_number','charter_date','client_id','total_amount_due','paid_amount','balance','status'])
    for r in rows:
        charter_id, reserve, cdate, client, due, paid, bal, status = r
        writer.writerow([charter_id, reserve or '', cdate, client, float(due or 0), float(paid or 0), float(bal or 0), status or ''])

print(f"Wrote {len(rows)} rows to {args.out}")

cur.close(); conn.close()

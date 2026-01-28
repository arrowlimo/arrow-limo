"""
List all 2012 charters with $0.01 outstanding balances (penny noise).

Criteria:
- charter_date in 2012
- balance = 0.01 (use tight range to be robust to numeric types)
- exclude cancelled if possible
- print count and detailed rows
"""
import psycopg2

LOW = 0.009
HIGH = 0.011

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

print("="*80)
print("2012 charters with $0.01 outstanding balance")
print("="*80)

conn = get_conn()
cur = conn.cursor()

# Determine cancellation filter dynamically
cur.execute("""
SELECT column_name FROM information_schema.columns
WHERE table_name='charters'
""")
cols = {r[0] for r in cur.fetchall()}

cancel_filter = ""
if 'cancelled' in cols:
    cancel_filter = "AND (cancelled IS NULL OR cancelled = FALSE)"
elif 'status' in cols:
    cancel_filter = "AND (status IS NULL OR status NOT ILIKE 'cancel%')"

query = f"""
SELECT charter_id, reserve_number, charter_date, client_id, balance, paid_amount, total_amount_due
FROM charters
WHERE charter_date >= DATE '2012-01-01'
  AND charter_date < DATE '2013-01-01'
  AND balance >= %s AND balance <= %s
  {cancel_filter}
ORDER BY charter_date, charter_id
"""

cur.execute(query, (LOW, HIGH))
rows = cur.fetchall()

print(f"Found {len(rows)} charter(s) with ~ $0.01 outstanding")

if rows:
    print(f"\n{'CharterID':<10} {'Reserve':<8} {'Date':<10} {'Client':<8} {'Balance':>10} {'Paid':>10} {'TotalDue':>10}")
    print('-'*75)
    for r in rows:
        charter_id, reserve_number, charter_date, client_id, balance, paid_amount, total_due = r
        print(f"{charter_id:<10} {str(reserve_number or ''):<8} {charter_date} {str(client_id or ''):<8} ${float(balance):9.2f} ${float(paid_amount or 0):9.2f} ${float(total_due or 0):9.2f}")

cur.close(); conn.close()
print("\n" + "="*80)
print("REPORT COMPLETE")
print("="*80)

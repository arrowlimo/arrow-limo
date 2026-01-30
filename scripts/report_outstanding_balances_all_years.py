"""
Report outstanding charter balances across all years.

Outputs per-year:
- Outstanding count (> $0.01)
- Total outstanding
- Penny-noise count (~$0.01)
- Optional: Top 5 by balance per year when non-zero

Years are detected from min/max charter_date in charters.
"""
import psycopg2

LOW = 0.009
HIGH = 0.011
THRESH = 0.01

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

print("="*100)
print("OUTSTANDING CHARTER BALANCES BY YEAR")
print("="*100)

conn = get_conn()
cur = conn.cursor()

cancel_filter = get_cancel_filter(cur)

# Determine min and max years
cur.execute("SELECT MIN(charter_date), MAX(charter_date) FROM charters WHERE charter_date IS NOT NULL")
min_date, max_date = cur.fetchone()
if not min_date or not max_date:
    print("No charter dates found.")
    exit(0)

start_year = min_date.year
end_year = max_date.year

print(f"Date range: {min_date} → {max_date} ({start_year}–{end_year})")

print("\nYear | >$0.01 Count | >$0.01 Total     | $0.01 Count")
print("-"*70)

years_with_issues = []

def year_summary(y):
    cur.execute(f"""
        SELECT COUNT(*), COALESCE(SUM(balance), 0)
        FROM charters
        WHERE charter_date >= DATE %s
          AND charter_date < DATE %s
          AND balance > %s
          {cancel_filter}
    """, (f"{y}-01-01", f"{y+1}-01-01", THRESH))
    cnt, total = cur.fetchone()

    cur.execute(f"""
        SELECT COUNT(*)
        FROM charters
        WHERE charter_date >= DATE %s
          AND charter_date < DATE %s
          AND balance >= %s AND balance <= %s
          {cancel_filter}
    """, (f"{y}-01-01", f"{y+1}-01-01", LOW, HIGH))
    penny_cnt = cur.fetchone()[0]
    return cnt, float(total or 0), penny_cnt

for y in range(start_year, end_year + 1):
    cnt, total, penny = year_summary(y)
    print(f"{y} | {cnt:11d} | ${total:15,.2f} | {penny:11d}")
    if cnt > 0 or penny > 0:
        years_with_issues.append((y, cnt, total, penny))

if years_with_issues:
    print("\n" + "="*100)
    print("DETAILS FOR YEARS WITH NON-ZERO COUNTS")
    print("="*100)
    for y, cnt, total, penny in years_with_issues:
        print(f"\nYear {y}: >$0.01={cnt}, total=${total:,.2f}, $0.01={penny}")
        # Show top 5 balances
        cur.execute(f"""
            SELECT charter_id, reserve_number, charter_date, client_id, balance, paid_amount, total_amount_due
            FROM charters
            WHERE charter_date >= DATE %s
              AND charter_date < DATE %s
              AND balance > %s
              {cancel_filter}
            ORDER BY balance DESC
            LIMIT 5
        """, (f"{y}-01-01", f"{y+1}-01-01", THRESH))
        tops = cur.fetchall()
        if tops:
            for r in tops:
                charter_id, reserve, cdate, client, bal, paid, due = r
                print(f"  #{charter_id} res {reserve or ''} on {cdate}: bal=${float(bal):,.2f}, paid=${float(paid or 0):,.2f}, due=${float(due or 0):,.2f}")
        else:
            print("  No >$0.01 details to show")

cur.close(); conn.close()

print("\n" + "="*100)
print("REPORT COMPLETE")
print("="*100)

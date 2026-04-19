"""
lms2026c_payment_vs_almsdata.py
================================
Core question: for every reserve number, does the total paid in LMS
match the total paid in almsdata?

Link chain:
  LMS   → Payment.Reserve_No  (direct — no intermediate table needed)
  ALMS  → charter_payments.charter_id  (stores the reserve number)
  ALMS  → charters.reserve_number      (master charter record)

Outputs (console + CSV):
  lms_alms_by_reserve.csv     — every reserve: LMS total vs ALMS total, diff
  lms_only_reserves.csv       — in LMS Reserve table but NOT in almsdata charters
  alms_only_reserves.csv      — in almsdata charters but NOT in LMS Reserve
"""

import pyodbc, psycopg2, psycopg2.extras, csv, decimal
from collections import defaultdict

LMS   = r"L:\lms2026c.mdb"
PG    = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
TOL   = decimal.Decimal("0.02")

# ── 1. LMS: load all Payment rows ──────────────────────────────────────────
print("Loading LMS payments ...")
lms_conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
lms_cur  = lms_conn.cursor()

# NOTE: filter to only reserves in scope (applied after lms_reserves is built below)
lms_cur.execute("SELECT Reserve_No, Amount FROM Payment")
lms_pay_raw = lms_cur.fetchall()
# lms_reserves filtered to 2007-2018 is built next; payment filter applied after

# ── 2. LMS: all Reserve records ─────────────────────────────────────────────
print("Loading LMS reserves ...")
lms_cur.execute("""
    SELECT Reserve_No, Name, Account_No, PU_Date, Balance, Cancelled FROM Reserve
    WHERE PU_Date >= #2007-01-01# AND PU_Date < #2019-01-01#
""")
lms_reserves = {}
for r in lms_cur.fetchall():
    res = str(r.Reserve_No).strip().zfill(6)
    lms_reserves[res] = {
        'name':      r.Name or '',
        'acct':      r.Account_No or '',
        'pu_date':   str(r.PU_Date)[:10] if r.PU_Date else '',
        'balance':   decimal.Decimal(str(r.Balance or 0)),
        'cancelled': bool(r.Cancelled),
    }
print(f"  {len(lms_reserves):,} LMS reserves in 2007-2018 date range")
lms_conn.close()

# Now aggregate LMS payments — only for in-scope reserves
lms_pay = defaultdict(decimal.Decimal)
lms_pay_count = defaultdict(int)
for r in lms_pay_raw:
    res = str(r.Reserve_No).strip().zfill(6)
    if res not in lms_reserves:
        continue
    amt = decimal.Decimal(str(r.Amount or 0))
    lms_pay[res]       += amt
    lms_pay_count[res] += 1
print(f"  {sum(lms_pay_count.values()):,} LMS payment rows across {len(lms_pay):,} 2007-2018 reserves")

# ── 3. ALMS: charter_payments grouped by reserve (charter_id) ───────────────
print("Loading almsdata charter_payments ...")
pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT cp.charter_id,
           SUM(cp.amount)  AS total,
           COUNT(*)        AS cnt
    FROM   charter_payments cp
    JOIN   charters c ON c.reserve_number = cp.charter_id
    WHERE  cp.charter_id IS NOT NULL AND cp.charter_id <> ''
      AND  c.charter_date >= '2007-01-01' AND c.charter_date < '2019-01-01'
    GROUP  BY cp.charter_id
""")
alms_pay = {}
for r in cur.fetchall():
    res = str(r['charter_id']).strip().zfill(6)
    alms_pay[res] = {
        'total': decimal.Decimal(str(r['total'] or 0)),
        'count': int(r['cnt']),
    }
print(f"  almsdata has payments for {len(alms_pay):,} unique reserves")

# ── 4. ALMS: charters (master list) ─────────────────────────────────────────
print("Loading almsdata charters ...")
cur.execute("""
    SELECT reserve_number, client_display_name, charter_date,
           cancelled, grand_total
    FROM   charters
    WHERE  reserve_number IS NOT NULL
      AND  charter_date >= '2007-01-01' AND charter_date < '2019-01-01'
""")
alms_charters = {}
for r in cur.fetchall():
    res = str(r['reserve_number']).strip().zfill(6)
    alms_charters[res] = {
        'client':    r['client_display_name'] or '',
        'date':      str(r['charter_date']) if r['charter_date'] else '',
        'cancelled': bool(r['cancelled']),
        'grand_total': decimal.Decimal(str(r['grand_total'] or 0)),
    }
print(f"  {len(alms_charters):,} almsdata charters")
pg.close()

# ── 5. Compare ───────────────────────────────────────────────────────────────
print("\nComparing ...")

all_reserves = sorted(set(lms_reserves.keys()) | set(alms_charters.keys()))

rows_matched   = []   # both systems, payment totals equal
rows_diff      = []   # both systems, payment totals differ
rows_lms_only  = []   # reserve in LMS but no charter in almsdata
rows_alms_only = []   # charter in almsdata but no reserve in LMS

for res in all_reserves:
    in_lms  = res in lms_reserves
    in_alms = res in alms_charters
    lms_total  = lms_pay.get(res, decimal.Decimal(0))
    alms_total = alms_pay.get(res, {}).get('total', decimal.Decimal(0))
    lms_cnt    = lms_pay_count.get(res, 0)
    alms_cnt   = alms_pay.get(res, {}).get('count', 0)
    diff       = lms_total - alms_total

    lms_r  = lms_reserves.get(res, {})
    alms_r = alms_charters.get(res, {})

    base = {
        'reserve_no':   res,
        'lms_client':   lms_r.get('name', ''),
        'alms_client':  alms_r.get('client', ''),
        'lms_date':     lms_r.get('pu_date', ''),
        'alms_date':    alms_r.get('date', ''),
        'lms_cancelled':  lms_r.get('cancelled', ''),
        'alms_cancelled': alms_r.get('cancelled', ''),
        'lms_pay_total':  float(lms_total),
        'alms_pay_total': float(alms_total),
        'lms_pay_count':  lms_cnt,
        'alms_pay_count': alms_cnt,
        'diff':           float(diff),
    }

    if in_lms and not in_alms:
        rows_lms_only.append(base)
    elif not in_lms and in_alms:
        rows_alms_only.append(base)
    elif abs(diff) <= TOL:
        rows_matched.append(base)
    else:
        rows_diff.append(base)

rows_diff.sort(key=lambda r: abs(r['diff']), reverse=True)

# ── 6. Console summary ───────────────────────────────────────────────────────
print()
print("=" * 65)
print("  LMS2026c  vs  almsdata  —  Payment reconciliation by reserve  (2007–2018)")
print("=" * 65)
print(f"  Total unique reserves (either system):  {len(all_reserves):,}")
print(f"  ✅ Both systems, payment totals MATCH:  {len(rows_matched):,}")
print(f"  ❌ Both systems, payment totals DIFFER: {len(rows_diff):,}")
print(f"  🔴 In LMS reserve but NOT in almsdata:  {len(rows_lms_only):,}")
print(f"  🔵 In almsdata but NOT in LMS reserve:  {len(rows_alms_only):,}")

if rows_diff:
    under = [r for r in rows_diff if r['diff'] > 0]
    over  = [r for r in rows_diff if r['diff'] < 0]
    print()
    print(f"  Of {len(rows_diff)} mismatches:")
    print(f"    {len(under):>4}  almsdata MISSING payments vs LMS  "
          f"(gap = ${sum(r['diff'] for r in under):>12,.2f})")
    print(f"    {len(over):>4}  almsdata has MORE than LMS         "
          f"(excess = ${abs(sum(r['diff'] for r in over)):>10,.2f})")

print()
print("  Top 15 largest mismatches:")
print(f"  {'Reserve':>8}  {'LMS Client':<22}  {'LMS Pay':>10}  {'ALMS Pay':>10}  {'Diff':>10}")
print("  " + "-" * 65)
for r in rows_diff[:15]:
    print(f"  {r['reserve_no']:>8}  {str(r['lms_client'])[:22]:<22}  "
          f"{r['lms_pay_total']:>10.2f}  {r['alms_pay_total']:>10.2f}  "
          f"{r['diff']:>+10.2f}")

# ── 7. CSV exports ───────────────────────────────────────────────────────────
FIELDS = ['reserve_no', 'lms_client', 'alms_client', 'lms_date', 'alms_date',
          'lms_cancelled', 'alms_cancelled', 'lms_pay_total', 'alms_pay_total',
          'lms_pay_count', 'alms_pay_count', 'diff']

def write_csv(path, data):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(data)
    print(f"  Written {path}  ({len(data):,} rows)")

print()
print("Writing CSVs ...")
all_rows = rows_diff + rows_matched + rows_lms_only + rows_alms_only
all_rows.sort(key=lambda r: abs(r['diff']), reverse=True)
write_csv(r'L:\limo\lms_alms_by_reserve.csv', all_rows)

lms_only_sorted = sorted(rows_lms_only, key=lambda r: r['lms_pay_total'], reverse=True)
write_csv(r'L:\limo\lms_only_reserves.csv', lms_only_sorted)

alms_only_sorted = sorted(rows_alms_only, key=lambda r: r['alms_pay_total'], reverse=True)
write_csv(r'L:\limo\alms_only_reserves.csv', alms_only_sorted)

print("Done.")

"""
compare_lms2026c_vs_almsdata.py
================================
Cross-references every charter payment in LMS2026c.mdb against almsdata
(PostgreSQL) to find:
  1. LMS reserves with NO matching charter in almsdata
  2. almsdata charters with NO matching LMS reserve
  3. Payment-total mismatches (LMS total vs almsdata total per reserve)
  4. Individual LMS payment rows with no matching row in charter_payments
  5. Summary counts / amounts

Output:
  - Console summary
  - lms_vs_alms_reserve_diff.csv       -- per-reserve payment total differences
  - lms_vs_alms_lms_only_reserves.csv  -- LMS reserves not found in almsdata
  - lms_vs_alms_alms_only_charters.csv -- almsdata charters not found in LMS  
  - lms_vs_alms_unmatched_payments.csv -- LMS payment rows with no ALMS match
"""
import pyodbc
import psycopg2
import psycopg2.extras
import csv
import decimal
from collections import defaultdict
from datetime import date

LMS_PATH = r"L:\lms2026c.mdb"
PG_DSN = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"

TOLERANCE = decimal.Decimal("0.02")   # treat differences <= 2 cents as equal

# ─────────────────────────────────────────────
# 1.  Load LMS data
# ─────────────────────────────────────────────
print("Connecting to LMS2026c.mdb ...")
lms_conn = pyodbc.connect(
    f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
)
lms_cur = lms_conn.cursor()

# All payments  (Payment table)
print("  Loading LMS Payment rows ...")
lms_cur.execute("""
    SELECT PaymentID, Reserve_No, Amount, Account_No, LastUpdated
    FROM Payment
    WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''
""")
lms_payments = lms_cur.fetchall()
print(f"  → {len(lms_payments):,} LMS payment rows")

# Aggregate per reserve
lms_pay_by_reserve = defaultdict(decimal.Decimal)
lms_pay_rows_by_reserve = defaultdict(list)
for row in lms_payments:
    res = str(row.Reserve_No).strip().zfill(6)
    amt = decimal.Decimal(str(row.Amount)) if row.Amount is not None else decimal.Decimal(0)
    lms_pay_by_reserve[res] += amt
    lms_pay_rows_by_reserve[res].append(row)

# All reserves (Reserve table) – just enough columns
print("  Loading LMS Reserve rows ...")
lms_cur.execute("""
    SELECT Reserve_No, Account_No, Name, PU_Date,
           Balance, Est_Charge, Cancelled, Closed
    FROM Reserve
    WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''
""")
lms_reserves_raw = lms_cur.fetchall()
print(f"  → {len(lms_reserves_raw):,} LMS reserves total")

lms_reserves = {}
for r in lms_reserves_raw:
    res = str(r.Reserve_No).strip().zfill(6)
    lms_reserves[res] = r

# All charges aggregated per reserve
print("  Loading LMS Charge rows ...")
lms_cur.execute("""
    SELECT Reserve_No, SUM(Amount * Rate) AS charge_total
    FROM Charge
    WHERE Reserve_No IS NOT NULL AND Reserve_No <> ''
    GROUP BY Reserve_No
""")
lms_charge_by_reserve = {}
for row in lms_cur.fetchall():
    res = str(row.Reserve_No).strip().zfill(6)
    lms_charge_by_reserve[res] = decimal.Decimal(str(row.charge_total or 0))

lms_conn.close()
print("  LMS load complete.\n")

# ─────────────────────────────────────────────
# 2.  Load almsdata (PostgreSQL)
# ─────────────────────────────────────────────
print("Connecting to almsdata (PostgreSQL) ...")
pg_conn = psycopg2.connect(PG_DSN)
pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# All charters
pg_cur.execute("""
    SELECT reserve_number, charter_id, client_name, charter_date,
           total_amount, is_cancelled
    FROM charters
    WHERE reserve_number IS NOT NULL
""")
alms_charters_raw = pg_cur.fetchall()
print(f"  → {len(alms_charters_raw):,} almsdata charters")
alms_charters = {str(r['reserve_number']).zfill(6): r for r in alms_charters_raw}

# All charter_payments aggregated per reserve
pg_cur.execute("""
    SELECT cp.charter_id AS reserve_no,
           SUM(cp.amount) AS pay_total,
           COUNT(*) AS pay_count
    FROM charter_payments cp
    WHERE cp.charter_id IS NOT NULL AND cp.charter_id <> ''
    GROUP BY cp.charter_id
""")
alms_pay_by_reserve = {}
for r in pg_cur.fetchall():
    res = str(r['reserve_no']).strip().zfill(6)
    alms_pay_by_reserve[res] = {
        'total': decimal.Decimal(str(r['pay_total'] or 0)),
        'count': r['pay_count'],
    }
print(f"  → {len(alms_pay_by_reserve):,} reserves with charter_payments")

# Individual charter_payment rows (for per-row matching)
pg_cur.execute("""
    SELECT id, charter_id, amount, payment_date, payment_method, payment_key, source
    FROM charter_payments
    WHERE charter_id IS NOT NULL AND charter_id <> ''
    ORDER BY charter_id, payment_date, amount
""")
alms_pay_rows = pg_cur.fetchall()
# Group by (reserve, amount, date) for matching LMS rows
alms_pay_lookup = defaultdict(list)
for r in alms_pay_rows:
    res = str(r['charter_id']).zfill(6)
    d = r['payment_date'].strftime('%Y-%m-%d') if r['payment_date'] else 'NULL'
    amt = decimal.Decimal(str(r['amount'] or 0))
    alms_pay_lookup[(res, amt, d)].append(r)

pg_conn.close()
print("  almsdata load complete.\n")

# ─────────────────────────────────────────────
# 3.  Cross-reference
# ─────────────────────────────────────────────
all_reserves = sorted(set(lms_reserves.keys()) | set(alms_charters.keys()))
print(f"Total unique reserves across both systems: {len(all_reserves):,}\n")

lms_only_reserves = []    # in LMS but not almsdata
alms_only_charters = []   # in almsdata but not LMS
reserve_diffs = []         # pay totals differ
matched_reserves = 0

for res in all_reserves:
    in_lms   = res in lms_reserves
    in_alms  = res in alms_charters
    lms_pay  = lms_pay_by_reserve.get(res, decimal.Decimal(0))
    alms_pay = alms_pay_by_reserve.get(res, {}).get('total', decimal.Decimal(0))
    lms_r    = lms_reserves.get(res)
    alms_c   = alms_charters.get(res)

    if in_lms and not in_alms:
        lms_only_reserves.append({
            'reserve_no': res,
            'lms_client': lms_r.Name if lms_r else '',
            'lms_res_date': str(lms_r.PU_Date)[:10] if lms_r and lms_r.PU_Date else '',
            'lms_cancelled': lms_r.Cancelled if lms_r else '',
            'lms_balance': float(lms_r.Balance) if lms_r and lms_r.Balance is not None else '',
            'lms_total':   float(lms_r.Est_Charge) if lms_r and lms_r.Est_Charge is not None else '',
            'lms_pay_total': float(lms_pay),
        })
    elif not in_lms and in_alms:
        alms_only_charters.append({
            'reserve_no': res,
            'alms_client': alms_c['client_name'],
            'alms_date': str(alms_c['charter_date']),
            'alms_cancelled': alms_c['is_cancelled'],
            'alms_total': float(alms_c['total_amount'] or 0),
            'alms_pay_total': float(alms_pay),
        })
    else:
        # In both — compare payment totals
        diff = lms_pay - alms_pay
        if abs(diff) > TOLERANCE:
            reserve_diffs.append({
                'reserve_no': res,
                'lms_client': lms_r.Name if lms_r else '',
                'alms_client': alms_c['client_name'] if alms_c else '',
                'lms_res_date': str(lms_r.PU_Date)[:10] if lms_r and lms_r.PU_Date else '',
                'alms_date': str(alms_c['charter_date']) if alms_c else '',
                'lms_cancelled': lms_r.Cancelled if lms_r else '',
                'alms_cancelled': alms_c['is_cancelled'] if alms_c else '',
                'lms_pay_total': float(lms_pay),
                'alms_pay_total': float(alms_pay),
                'diff': float(diff),
                'lms_alms_client_match': (
                    (lms_r.Name or '').lower()[:8] ==
                    ((alms_c['client_name'] or '') if alms_c else '').lower()[:8]
                ),
            })
        else:
            matched_reserves += 1

print(f"Results:")
print(f"  ✅ Reserves matching in both systems (pay total OK): {matched_reserves:,}")
print(f"  ⚠️  Reserves with payment total MISMATCH:          {len(reserve_diffs):,}")
print(f"  🔴 LMS reserves NOT in almsdata charters:          {len(lms_only_reserves):,}")
print(f"  🔵 almsdata charters NOT in LMS:                   {len(alms_only_charters):,}")

# Subtotals for diff
if reserve_diffs:
    underpaid_alms  = [r for r in reserve_diffs if r['diff'] > 0]   # LMS > ALMS
    overpaid_alms   = [r for r in reserve_diffs if r['diff'] < 0]   # ALMS > LMS
    print(f"\n  Of {len(reserve_diffs)} mismatched reserves:")
    print(f"    {len(underpaid_alms)} where almsdata has LESS payments than LMS "
          f"(total gap: ${sum(r['diff'] for r in underpaid_alms):,.2f})")
    print(f"    {len(overpaid_alms)} where almsdata has MORE payments than LMS "
          f"(total excess: ${abs(sum(r['diff'] for r in overpaid_alms)):,.2f})")

# ─────────────────────────────────────────────
# 4.  Per-payment-row match  (LMS rows vs ALMS rows by res+amt+date)
# ─────────────────────────────────────────────
print("\nMatching individual LMS payment rows to almsdata rows ...")
unmatched_lms_payments = []
for pay_row in lms_payments:
    res = str(pay_row.Reserve_No).strip().zfill(6)
    amt = decimal.Decimal(str(pay_row.Amount)) if pay_row.Amount is not None else decimal.Decimal(0)
    d   = pay_row.LastUpdated.strftime('%Y-%m-%d') if pay_row.LastUpdated else 'NULL'
    # Try exact res+amt+date
    key = (res, amt, d)
    if key in alms_pay_lookup and alms_pay_lookup[key]:
        alms_pay_lookup[key].pop(0)   # consume one matching row
    else:
        # Try res+amt only (date might differ slightly)
        found = False
        for d2 in list(alms_pay_lookup.keys()):
            if d2[0] == res and d2[1] == amt:
                alms_pay_lookup[d2].pop(0)
                if not alms_pay_lookup[d2]:
                    del alms_pay_lookup[d2]
                found = True
                break
        if not found:
            lms_r = lms_reserves.get(res)
            unmatched_lms_payments.append({
                'PaymentID': pay_row.PaymentID,
                'reserve_no': res,
                'amount': float(amt),
                'lms_date': d,
                'lms_client': lms_r.Name if lms_r else '',
                'lms_res_date': str(lms_r.PU_Date)[:10] if lms_r and lms_r.PU_Date else '',
                'in_alms_charter': res in alms_charters,
                'alms_pay_total': float(alms_pay_by_reserve.get(res, {}).get('total', 0)),
                'lms_pay_total': float(lms_pay_by_reserve.get(res, 0)),
            })

print(f"  LMS payment rows with NO exact match in almsdata: {len(unmatched_lms_payments):,}")

# ─────────────────────────────────────────────
# 5.  Write CSVs
# ─────────────────────────────────────────────
def write_csv(path, rows, fieldnames=None):
    if not rows:
        print(f"  (empty — skipping {path})")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  Written: {path}  ({len(rows):,} rows)")

print("\nWriting CSV reports ...")
# Sort by diff magnitude
reserve_diffs_sorted = sorted(reserve_diffs, key=lambda r: abs(r['diff']), reverse=True)
write_csv(r'L:\limo\lms_vs_alms_reserve_diff.csv', reserve_diffs_sorted)
write_csv(r'L:\limo\lms_vs_alms_lms_only_reserves.csv', lms_only_reserves)
write_csv(r'L:\limo\lms_vs_alms_alms_only_charters.csv', alms_only_charters)
write_csv(r'L:\limo\lms_vs_alms_unmatched_payments.csv', unmatched_lms_payments)

# ─────────────────────────────────────────────
# 6.  Quick top-10 worst mismatches
# ─────────────────────────────────────────────
if reserve_diffs_sorted:
    print("\n=== Top 10 largest payment mismatches (|LMS - ALMS|) ===")
    print(f"{'Reserve':>8}  {'LMS Client':<25}  {'LMS Pay':>10}  {'ALMS Pay':>10}  {'Diff':>10}  {'Date'}")
    for r in reserve_diffs_sorted[:10]:
        print(f"{r['reserve_no']:>8}  {str(r['lms_client']):<25}  "
              f"{r['lms_pay_total']:>10.2f}  {r['alms_pay_total']:>10.2f}  "
              f"{r['diff']:>10.2f}  {r['lms_res_date']}")

print("\nDone.")

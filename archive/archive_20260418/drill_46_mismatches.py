"""
drill_46_mismatches.py
======================
For each of the 46 mismatched reserves (2007-2018), show:
  - LMS individual payment rows
  - ALMS individual payment rows
  - Sibling reserves (same account/client, ±30 days) that might share the payment
  - Flag where almsdata amount = N × LMS amount  (multi-charter spanning issue)
"""
import pyodbc, psycopg2, psycopg2.extras, csv, decimal
from collections import defaultdict
from datetime import timedelta, datetime

LMS = r"L:\lms2026c.mdb"
PG  = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
TOL = decimal.Decimal("0.02")

# ── Load LMS 2007-2018 reserves & payments ───────────────────────────────────
lms_conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
lms_cur  = lms_conn.cursor()

lms_cur.execute("""
    SELECT Reserve_No, Name, Account_No, PU_Date, Balance, Cancelled
    FROM Reserve
    WHERE PU_Date >= #2007-01-01# AND PU_Date < #2019-01-01#
""")
lms_reserves = {}
for r in lms_cur.fetchall():
    res = str(r.Reserve_No).strip().zfill(6)
    lms_reserves[res] = {
        'name': r.Name or '', 'acct': r.Account_No or '',
        'pu_date': r.PU_Date, 'cancelled': bool(r.Cancelled),
    }

lms_cur.execute("SELECT Reserve_No, Amount, Key, LastUpdated FROM Payment")
lms_pay_rows_by_res = defaultdict(list)
lms_pay_total = defaultdict(decimal.Decimal)
for r in lms_cur.fetchall():
    res = str(r.Reserve_No).strip().zfill(6)
    if res not in lms_reserves:
        continue
    amt = decimal.Decimal(str(r.Amount or 0))
    lms_pay_rows_by_res[res].append({
        'amount': amt, 'key': r.Key or '',
        'date': str(r.LastUpdated)[:10] if r.LastUpdated else '',
    })
    lms_pay_total[res] += amt
lms_conn.close()

# ── Load ALMS 2007-2018 ───────────────────────────────────────────────────────
pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT cp.id, cp.charter_id AS reserve_no, cp.amount, cp.payment_date,
           cp.payment_method, cp.source, cp.payment_key
    FROM   charter_payments cp
    JOIN   charters c ON c.reserve_number = cp.charter_id
    WHERE  c.charter_date >= '2007-01-01' AND c.charter_date < '2019-01-01'
      AND  cp.charter_id IS NOT NULL AND cp.charter_id <> ''
    ORDER  BY cp.charter_id, cp.payment_date, cp.amount
""")
alms_pay_rows_by_res = defaultdict(list)
alms_pay_total = defaultdict(decimal.Decimal)
for r in cur.fetchall():
    res = str(r['reserve_no']).zfill(6)
    alms_pay_rows_by_res[res].append(dict(r))
    alms_pay_total[res] += decimal.Decimal(str(r['amount'] or 0))

cur.execute("""
    SELECT reserve_number, client_display_name, charter_date, account_number, cancelled
    FROM   charters
    WHERE  charter_date >= '2007-01-01' AND charter_date < '2019-01-01'
      AND  reserve_number IS NOT NULL
""")
alms_charters = {}
for r in cur.fetchall():
    res = str(r['reserve_number']).zfill(6)
    alms_charters[res] = dict(r)
pg.close()

# ── Build the 46-mismatch list ────────────────────────────────────────────────
mismatches = []
for res in sorted(set(lms_reserves.keys()) | set(alms_charters.keys())):
    lt = lms_pay_total.get(res, decimal.Decimal(0))
    at = alms_pay_total.get(res, decimal.Decimal(0))
    diff = lt - at
    if abs(diff) > TOL:
        mismatches.append((res, lt, at, diff))

mismatches.sort(key=lambda x: abs(x[3]), reverse=True)
print(f"Mismatched reserves: {len(mismatches)}\n")

# ── For each mismatch, find siblings (same account, ±60 days) ────────────────
# Build account → [reserves] map from LMS
acct_to_reserves = defaultdict(list)
for res, info in lms_reserves.items():
    acct_to_reserves[info['acct']].append(res)

# ── Detailed report ───────────────────────────────────────────────────────────
csv_rows = []

for res, lms_tot, alms_tot, diff in mismatches:
    lms_r  = lms_reserves.get(res, {})
    alms_r = alms_charters.get(res, {})

    client  = lms_r.get('name') or (alms_r.get('client_display_name') if alms_r else '') or ''
    pu_date = lms_r.get('pu_date')
    acct    = lms_r.get('acct', '')

    # Detect ratio (is alms = N × lms?)
    ratio_flag = ''
    if lms_tot > 0 and alms_tot > 0:
        ratio = alms_tot / lms_tot
        if abs(ratio - round(ratio)) < decimal.Decimal('0.02'):
            n = int(round(ratio))
            if n >= 2:
                ratio_flag = f'ALMS={n}x LMS (multi-charter?)'
    elif lms_tot > 0 and alms_tot == 0:
        ratio_flag = 'ALMS HAS NO PAYMENT'
    elif lms_tot == 0 and alms_tot > 0:
        ratio_flag = 'LMS HAS NO PAYMENT'

    # Sibling reserves (same account, within 60 days)
    siblings = []
    if acct and pu_date:
        for sib in acct_to_reserves.get(acct, []):
            if sib == res:
                continue
            sib_date = lms_reserves[sib]['pu_date']
            if sib_date and abs((sib_date - pu_date).days) <= 60:
                sib_lms  = lms_pay_total.get(sib, decimal.Decimal(0))
                sib_alms = alms_pay_total.get(sib, decimal.Decimal(0))
                siblings.append(f"{sib}(LMS${sib_lms:.2f}/ALMS${sib_alms:.2f})")

    print(f"{'='*70}")
    print(f"Reserve {res}  |  {client}  |  {str(pu_date)[:10] if pu_date else alms_r.get('date','') if alms_r else ''}")
    print(f"  LMS total: ${lms_tot:>10.2f}   ALMS total: ${alms_tot:>10.2f}   Diff: ${diff:>+10.2f}")
    if ratio_flag:
        print(f"  *** {ratio_flag}")
    if siblings:
        print(f"  Siblings (same acct, ±60d): {', '.join(siblings)}")

    print(f"  LMS payments:")
    for p in lms_pay_rows_by_res.get(res, []):
        print(f"    ${p['amount']:>10.2f}  date={p['date']}  key={p['key']}")
    if not lms_pay_rows_by_res.get(res):
        print(f"    (none)")

    print(f"  ALMS payments:")
    for p in alms_pay_rows_by_res.get(res, []):
        d = str(p['payment_date']) if p['payment_date'] else 'NULL'
        print(f"    ${decimal.Decimal(str(p['amount'])):>10.2f}  date={d}  method={p['payment_method']}  source={p['source']}  id={p['id']}")
    if not alms_pay_rows_by_res.get(res):
        print(f"    (none)")

    csv_rows.append({
        'reserve_no':    res,
        'client':        client,
        'pu_date':       str(pu_date)[:10] if pu_date else '',
        'lms_total':     float(lms_tot),
        'alms_total':    float(alms_tot),
        'diff':          float(diff),
        'flag':          ratio_flag,
        'siblings':      ' | '.join(siblings),
        'lms_payments':  ' | '.join(f"${p['amount']} {p['date']} key={p['key']}" for p in lms_pay_rows_by_res.get(res, [])),
        'alms_payments': ' | '.join(f"${p['amount']} {p['payment_date']} id={p['id']}" for p in alms_pay_rows_by_res.get(res, [])),
    })

with open(r'L:\limo\mismatch_46_detail.csv', 'w', newline='', encoding='utf-8') as f:
    import csv as _csv
    w = _csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
    w.writeheader()
    w.writerows(csv_rows)

print(f"\nWritten: L:\\limo\\mismatch_46_detail.csv")

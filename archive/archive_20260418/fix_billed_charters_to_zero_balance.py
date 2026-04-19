import pyodbc
import psycopg2
import psycopg2.extras
from decimal import Decimal
from collections import Counter

PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
LMS = r"L:\lms2026c.mdb"
TOL = Decimal('0.02')
DRY_RUN = False

pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# 1) Find billed charters in 2007-2018 whose paid total doesn't zero out invoice
cur.execute("""
WITH p AS (
  SELECT charter_id AS reserve_number, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL AND charter_id <> ''
  GROUP BY charter_id
)
SELECT
  c.reserve_number,
  c.client_display_name,
  c.charter_date,
  COALESCE(c.grand_total,0) AS invoice_total,
  COALESCE(p.paid_total,0) AS paid_total,
  COALESCE(c.grand_total,0) - COALESCE(p.paid_total,0) AS balance
FROM charters c
LEFT JOIN p ON p.reserve_number = c.reserve_number
WHERE c.charter_date >= '2007-01-01' AND c.charter_date < '2019-01-01'
  AND COALESCE(c.grand_total,0) > 0
  AND ABS(COALESCE(c.grand_total,0) - COALESCE(p.paid_total,0)) > %s
ORDER BY c.reserve_number
""", (TOL,))
underpaid = cur.fetchall()

print(f"Billed charters with non-zero balance: {len(underpaid)}")

# 2) Load LMS payments for these reserves
reserves = [r['reserve_number'] for r in underpaid]
res_set = set(reserves)

lms_conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
lms_cur = lms_conn.cursor()
lms_cur.execute("SELECT Reserve_No, Amount, Key, LastUpdated FROM Payment")
lms_rows_by_res = {r: [] for r in reserves}
for row in lms_cur.fetchall():
    res = str(row.Reserve_No).strip().zfill(6)
    if res in res_set:
        lms_rows_by_res[res].append({
            'amount': Decimal(str(row.Amount or 0)),
            'key': str(row.Key or '').strip(),
            'date': row.LastUpdated.date().isoformat() if row.LastUpdated else None,
        })
lms_conn.close()

# 3) Load existing ALMS rows for these reserves
alms_rows_by_res = {}
for res in reserves:
    cur.execute("""
        SELECT id, amount, payment_date, payment_key, payment_method, source
        FROM charter_payments
        WHERE charter_id = %s
        ORDER BY id
    """, (res,))
    alms_rows_by_res[res] = cur.fetchall()

# 4) For each reserve, import missing LMS rows by payment_key first, then amount-count fallback
inserts = []
for r in underpaid:
    res = r['reserve_number']
    client = r['client_display_name'] or ''
    lms_rows = lms_rows_by_res.get(res, [])
    alms_rows = alms_rows_by_res.get(res, [])

    # Existing key set in ALMS
    existing_keys = set()
    for a in alms_rows:
        k = (a['payment_key'] or '').strip()
        if k:
            existing_keys.add(k)

    # Existing amounts counter fallback
    existing_amounts = Counter([Decimal(str(a['amount'] or 0)) for a in alms_rows])

    reserve_inserts = []
    for lp in sorted(lms_rows, key=lambda x: (x['date'] or '0000-00-00', x['amount'])):
        k = lp['key']
        amt = lp['amount']
        dt = lp['date']

        matched = False
        if k and k in existing_keys:
            matched = True
        else:
            # fallback: if same amount occurrences already present, treat as matched
            if existing_amounts[amt] > 0:
                existing_amounts[amt] -= 1
                matched = True

        if not matched:
            reserve_inserts.append((res, amt, dt, k, client))

    # Keep only inserts that move balance toward zero, never overshoot
    if reserve_inserts:
        bal = Decimal(str(r['balance']))
        if bal > 0:
            added = Decimal('0')
            for ins in reserve_inserts:
                amt = ins[1]
                if amt <= 0:
                    continue
                if added + amt - bal > TOL:
                    continue
                inserts.append(ins)
                added += amt
        elif bal < 0:
            added = Decimal('0')
            for ins in reserve_inserts:
                amt = ins[1]
                if amt >= 0:
                    continue
                if abs(added + amt) - abs(bal) > TOL:
                    continue
                inserts.append(ins)
                added += amt

print(f"Planned inserts from LMS: {len(inserts)}")
for ins in inserts:
    print(f"  {ins[0]}  amt={ins[1]}  date={ins[2]}  key={ins[3]}")

if not DRY_RUN and inserts:
    sql = """
    INSERT INTO charter_payments
      (charter_id, amount, payment_date, payment_method, payment_key, source, client_name)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    for res, amt, dt, key, client in inserts:
        method = 'unknown'
        src = 'lms_billed_balance_fix_20260322'
        cur.execute(sql, (res, amt, dt, method, key if key else None, src, client))
    pg.commit()
    print(f"Inserted {len(inserts)} rows.")
else:
    print("Dry run or no inserts; no DB changes.")

# 5) Show remaining billed non-zero balances
cur.execute("""
WITH p AS (
  SELECT charter_id AS reserve_number, SUM(amount) AS paid_total
  FROM charter_payments
  WHERE charter_id IS NOT NULL AND charter_id <> ''
  GROUP BY charter_id
)
SELECT c.reserve_number, c.charter_date, c.client_display_name,
       COALESCE(c.grand_total,0) AS invoice_total,
       COALESCE(p.paid_total,0) AS paid_total,
       COALESCE(c.grand_total,0) - COALESCE(p.paid_total,0) AS balance
FROM charters c
LEFT JOIN p ON p.reserve_number = c.reserve_number
WHERE c.charter_date >= '2007-01-01' AND c.charter_date < '2019-01-01'
  AND COALESCE(c.grand_total,0) > 0
  AND ABS(COALESCE(c.grand_total,0) - COALESCE(p.paid_total,0)) > %s
ORDER BY ABS(COALESCE(c.grand_total,0) - COALESCE(p.paid_total,0)) DESC, c.reserve_number
""", (TOL,))
remaining = cur.fetchall()
print(f"Remaining billed non-zero balances: {len(remaining)}")
for r in remaining[:20]:
    print(f"  {r['reserve_number']}  invoice={Decimal(str(r['invoice_total'])):.2f}  paid={Decimal(str(r['paid_total'])):.2f}  bal={Decimal(str(r['balance'])):.2f}")

pg.close()

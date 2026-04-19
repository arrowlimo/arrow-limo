import pyodbc
import psycopg2
import psycopg2.extras
from decimal import Decimal
from datetime import timedelta

LMS = r"L:\lms2026c.mdb"
PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"
TARGETS = ['013603', '014215', '001188', '001918', '013963']

# ----- LMS -----
lms_conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
lms_cur = lms_conn.cursor()

# Load Reserve rows for targets
q_marks = ','.join(['?'] * len(TARGETS))
lms_cur.execute(f"""
SELECT Reserve_No, Name, Account_No, PU_Date, Cancelled, Invoice_Dt, Invoice_No, Balance, Est_Charge
FROM Reserve
WHERE Reserve_No IN ({q_marks})
ORDER BY Reserve_No
""", TARGETS)
lms_res = {str(r.Reserve_No).zfill(6): r for r in lms_cur.fetchall()}

# Load all payments for target reserves
lms_cur.execute(f"""
SELECT Reserve_No, Amount, [Key], LastUpdated
FROM Payment
WHERE Reserve_No IN ({q_marks})
ORDER BY Reserve_No, LastUpdated, Amount
""", TARGETS)
lms_target_pay = {}
for r in TARGETS:
    lms_target_pay[r] = []
for p in lms_cur.fetchall():
    rn = str(p.Reserve_No).zfill(6)
    lms_target_pay[rn].append({
        'amount': Decimal(str(p.Amount or 0)),
        'key': str(getattr(p, 'Key', '') or ''),
        'date': str(p.LastUpdated)[:10] if p.LastUpdated else None,
    })

# Load charge totals for targets
lms_cur.execute(f"""
SELECT Reserve_No, SUM(Amount * Rate) AS charge_total
FROM Charge
WHERE Reserve_No IN ({q_marks})
GROUP BY Reserve_No
""", TARGETS)
lms_target_charge = {str(r.Reserve_No).zfill(6): Decimal(str(r.charge_total or 0)) for r in lms_cur.fetchall()}

# For each target, find nearby reserves (same account within +/- 120 days)
lms_neighbors = {r: [] for r in TARGETS}
for r in TARGETS:
    row = lms_res.get(r)
    if not row:
        continue
    acct = str(row.Account_No or '').strip()
    pu = row.PU_Date
    if not acct or not pu:
        continue

    start = pu - timedelta(days=120)
    end = pu + timedelta(days=120)
    lms_cur.execute("""
    SELECT Reserve_No, Name, Account_No, PU_Date, Cancelled, Est_Charge, Balance
    FROM Reserve
    WHERE Account_No = ?
      AND PU_Date >= ?
      AND PU_Date <= ?
    ORDER BY PU_Date, Reserve_No
    """, (acct, start, end))

    nearby = lms_cur.fetchall()
    if not nearby:
        continue

    # Get payment totals for these nearby reserves
    nearby_res = [str(n.Reserve_No).zfill(6) for n in nearby]
    q2 = ','.join(['?'] * len(nearby_res))
    lms_cur.execute(f"""
    SELECT Reserve_No, SUM(Amount) AS pay_total, COUNT(*) AS pay_rows
    FROM Payment
    WHERE Reserve_No IN ({q2})
    GROUP BY Reserve_No
    """, nearby_res)
    pay_map = {str(x.Reserve_No).zfill(6): (Decimal(str(x.pay_total or 0)), int(x.pay_rows or 0)) for x in lms_cur.fetchall()}

    for n in nearby:
        rn = str(n.Reserve_No).zfill(6)
        p_tot, p_cnt = pay_map.get(rn, (Decimal('0'), 0))
        lms_neighbors[r].append({
            'reserve': rn,
            'name': str(n.Name or ''),
            'pu_date': str(n.PU_Date)[:10] if n.PU_Date else None,
            'cancelled': bool(n.Cancelled),
            'est_charge': Decimal(str(n.Est_Charge or 0)),
            'balance': Decimal(str(n.Balance or 0)),
            'pay_total': p_tot,
            'pay_rows': p_cnt,
        })

lms_conn.close()

# ----- ALMS -----
pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# target charters
cur.execute("""
SELECT reserve_number, charter_date, client_display_name, account_number,
       cancelled, grand_total, paid_amount, balance_owing, nrr_received, nrr_amount,
       nrd_received, nrd_amount
FROM charters
WHERE reserve_number = ANY(%s)
ORDER BY reserve_number
""", (TARGETS,))
alms_res = {str(r['reserve_number']).zfill(6): r for r in cur.fetchall()}

# target payments
cur.execute("""
SELECT id, charter_id, amount, payment_date, payment_method, payment_key, source
FROM charter_payments
WHERE charter_id = ANY(%s)
ORDER BY charter_id, payment_date, id
""", (TARGETS,))
alms_pay = {r: [] for r in TARGETS}
for p in cur.fetchall():
    rn = str(p['charter_id']).zfill(6)
    alms_pay[rn].append(p)

# neighbors in ALMS by account_number +/- 120 days
alms_neighbors = {r: [] for r in TARGETS}
for r in TARGETS:
    row = alms_res.get(r)
    if not row:
        continue
    acct = row.get('account_number')
    dt = row.get('charter_date')
    if not acct or not dt:
        continue

    cur.execute("""
    WITH p AS (
      SELECT charter_id AS reserve_number, SUM(amount) AS pay_total
      FROM charter_payments
      WHERE charter_id IS NOT NULL AND charter_id <> ''
      GROUP BY charter_id
    )
    SELECT c.reserve_number, c.charter_date, c.client_display_name,
           c.cancelled, COALESCE(c.grand_total,0) AS grand_total,
           COALESCE(p.pay_total,0) AS pay_total,
           (COALESCE(c.grand_total,0) - COALESCE(p.pay_total,0)) AS calc_balance
    FROM charters c
    LEFT JOIN p ON p.reserve_number = c.reserve_number
    WHERE c.account_number = %s
      AND c.charter_date >= %s::date - interval '120 days'
      AND c.charter_date <= %s::date + interval '120 days'
    ORDER BY c.charter_date, c.reserve_number
    """, (acct, dt, dt))
    alms_neighbors[r] = cur.fetchall()

pg.close()

# ----- Report -----
print("DEEP DIVE: 5 zero-billed charters with payments")
print("=" * 72)

for r in TARGETS:
    print("\n" + "-" * 72)
    print(f"Reserve {r}")

    lr = lms_res.get(r)
    ar = alms_res.get(r)

    if lr:
        print(f"LMS: name={lr.Name or ''} acct={lr.Account_No or ''} pu={str(lr.PU_Date)[:10] if lr.PU_Date else ''} cancelled={bool(lr.Cancelled)} est_charge={Decimal(str(lr.Est_Charge or 0)):.2f} balance={Decimal(str(lr.Balance or 0)):.2f}")
    else:
        print("LMS: reserve not found")

    if ar:
        print(f"ALMS: client={ar['client_display_name'] or ''} acct={ar.get('account_number') or ''} date={str(ar['charter_date'])[:10] if ar.get('charter_date') else ''} cancelled={bool(ar.get('cancelled'))} grand_total={Decimal(str(ar.get('grand_total') or 0)):.2f} paid_amount_field={Decimal(str(ar.get('paid_amount') or 0)):.2f} balance_owing_field={Decimal(str(ar.get('balance_owing') or 0)):.2f} nrr={bool(ar.get('nrr_received'))}/{Decimal(str(ar.get('nrr_amount') or 0)):.2f} nrd={bool(ar.get('nrd_received'))}/{Decimal(str(ar.get('nrd_amount') or 0)):.2f}")
    else:
        print("ALMS: charter not found")

    lms_p = lms_target_pay.get(r, [])
    alms_p = alms_pay.get(r, [])
    lms_sum = sum((x['amount'] for x in lms_p), Decimal('0'))
    alms_sum = sum((Decimal(str(x['amount'] or 0)) for x in alms_p), Decimal('0'))

    print(f"LMS payments: count={len(lms_p)} total={lms_sum:.2f}")
    for p in lms_p[:10]:
        print(f"  LMS  {p['date']}  amt={p['amount']:.2f}  key={p['key']}")

    print(f"ALMS payments: count={len(alms_p)} total={alms_sum:.2f}")
    for p in alms_p[:15]:
        print(f"  ALMS {str(p['payment_date']) if p['payment_date'] else ''}  amt={Decimal(str(p['amount'] or 0)):.2f}  method={p['payment_method'] or ''}  source={p['source'] or ''}  key={p['payment_key'] or ''}  id={p['id']}")

    print("Nearby LMS reserves (same account +/-120d):")
    for n in lms_neighbors.get(r, [])[:30]:
        marker = "*" if n['reserve'] == r else " "
        print(f"  {marker}{n['reserve']}  {n['pu_date']}  est={n['est_charge']:.2f}  paid={n['pay_total']:.2f}  bal={n['balance']:.2f}  cancelled={n['cancelled']}  {n['name'][:30]}")

    print("Nearby ALMS charters (same account +/-120d):")
    for n in alms_neighbors.get(r, [])[:30]:
        marker = "*" if str(n['reserve_number']).zfill(6) == r else " "
        print(f"  {marker}{str(n['reserve_number']).zfill(6)}  {str(n['charter_date'])[:10]}  gt={Decimal(str(n['grand_total'] or 0)):.2f}  paid={Decimal(str(n['pay_total'] or 0)):.2f}  bal={Decimal(str(n['calc_balance'] or 0)):.2f}  cancelled={bool(n['cancelled'])}  {(n['client_display_name'] or '')[:30]}")

print("\nDone.")

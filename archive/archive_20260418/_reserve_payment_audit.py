from collections import Counter, defaultdict
from decimal import Decimal
import psycopg2
import pyodbc

RESERVES = ['006341','012144','006311','012237','006318','007504']

pg = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
ac = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")


def fmt_amount(v):
    if v is None:
        return 'NULL'
    return f"{Decimal(v):.2f}"


def fmt_dt(v):
    if v is None:
        return 'NULL'
    try:
        return v.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        try:
            return v.strftime('%Y-%m-%d')
        except Exception:
            return str(v)


def date_only(v):
    if v is None:
        return None
    try:
        return v.date().isoformat()
    except Exception:
        try:
            return v.isoformat()
        except Exception:
            s = str(v)
            return s[:10]


def norm_key(v):
    return '' if v is None else str(v).strip()

pg_cur = pg.cursor()
placeholders = ','.join(['%s'] * len(RESERVES))

pg_cur.execute(f"""
    SELECT reserve_number, charter_id, charter_date, status, total_amount_due, amount_paid, balance_owing, payment_status
    FROM charters
    WHERE reserve_number IN ({placeholders})
    ORDER BY reserve_number, charter_date NULLS LAST, charter_id
""", RESERVES)
charters = defaultdict(list)
for row in pg_cur.fetchall():
    charters[row[0]].append(row[1:])

pg_cur.execute(f"""
    SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method, notes
    FROM payments
    WHERE reserve_number IN ({placeholders})
    ORDER BY reserve_number, payment_date NULLS LAST, payment_id
""", RESERVES)
local_payments = defaultdict(list)
for row in pg_cur.fetchall():
    local_payments[row[0]].append(row[1:])

pg_cur.execute(f"""
    SELECT c.reserve_number, cp.id, cp.payment_id, cp.charter_id, cp.charter_date, cp.payment_date, cp.amount, cp.payment_method, cp.payment_key, cp.source
    FROM charter_payments cp
    JOIN charters c ON c.charter_id::text = cp.charter_id
    WHERE c.reserve_number IN ({placeholders})
    ORDER BY c.reserve_number, cp.payment_date NULLS LAST, cp.id
""", RESERVES)
local_cp = defaultdict(list)
for row in pg_cur.fetchall():
    local_cp[row[0]].append(row[1:])

ac_cur = ac.cursor()
qmarks = ','.join(['?'] * len(RESERVES))
ac_cur.execute(f"""
    SELECT Reserve_No, PaymentID, [Key], LastUpdated, Amount
    FROM Payment
    WHERE Reserve_No IN ({qmarks})
    ORDER BY Reserve_No, LastUpdated, PaymentID
""", RESERVES)
lms_payments = defaultdict(list)
for row in ac_cur.fetchall():
    lms_payments[str(row[0])].append((row[1], row[2], row[3], row[4]))

for reserve in RESERVES:
    lp = local_payments.get(reserve, [])
    cp = local_cp.get(reserve, [])
    lm = lms_payments.get(reserve, [])
    ch = charters.get(reserve, [])

    print(f"RESERVE {reserve}")
    print('  Charter summary:')
    if ch:
        for r in ch:
            print(f"    charter_id={r[0]} date={fmt_dt(r[1])} status={r[2]} total_due={fmt_amount(r[3])} amount_paid={fmt_amount(r[4])} balance_owing={fmt_amount(r[5])} payment_status={r[6]}")
    else:
        print('    <none>')

    print('  Local payments:')
    if lp:
        for r in lp:
            print(f"    payment_id={r[0]} key={r[1]} payment_date={fmt_dt(r[2])} amount={fmt_amount(r[3])} method={r[4]} notes={repr(r[5])}")
    else:
        print('    <none>')

    print('  Local charter_payments:')
    if cp:
        for r in cp:
            print(f"    id={r[0]} payment_id={r[1]} charter_id={r[2]} charter_date={fmt_dt(r[3])} payment_date={fmt_dt(r[4])} amount={fmt_amount(r[5])} method={r[6]} key={r[7]} source={r[8]}")
    else:
        print('    <none>')

    print('  LMS Payment rows:')
    if lm:
        for r in lm:
            print(f"    PaymentID={r[0]} Key={r[1]} LastUpdated={fmt_dt(r[2])} Amount={fmt_amount(r[3])}")
    else:
        print('    <none>')

    local_total = sum((Decimal(r[3]) for r in lp), Decimal('0'))
    lms_total = sum((Decimal(r[3]) for r in lm), Decimal('0'))
    print(f"  Totals: local_payments={fmt_amount(local_total)} ({len(lp)} rows); LMS={fmt_amount(lms_total)} ({len(lm)} rows)")

    local_counter = Counter((norm_key(r[1]), date_only(r[2]), fmt_amount(r[3])) for r in lp)
    lms_counter = Counter((norm_key(r[1]), date_only(r[2]), fmt_amount(r[3])) for r in lm)
    extras = []
    for pat, cnt in local_counter.items():
        diff = cnt - lms_counter.get(pat, 0)
        if diff > 0:
            ids = [str(r[0]) for r in lp if (norm_key(r[1]), date_only(r[2]), fmt_amount(r[3])) == pat][:diff]
            extras.append((pat, diff, ids))
    if extras:
        print('  Extra local payment patterns not found in LMS: YES')
        for pat, diff, ids in extras:
            print(f"    key={pat[0]!r} date={pat[1]} amount={pat[2]} extra_count={diff} local_payment_ids={','.join(ids)}")
    else:
        print('  Extra local payment patterns not found in LMS: NO')
    print()

pg.close()
ac.close()

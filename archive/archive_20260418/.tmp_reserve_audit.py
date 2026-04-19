import psycopg2
from collections import defaultdict

TARGET = ['012154','012574','013357']
TARGET_NORM = {t.lstrip('0') for t in TARGET}

conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password="ArrowLimousine", port=5432)
cur = conn.cursor()

# 1) Charter headers
cur.execute('''
select charter_id, reserve_number::text, charter_date, total_amount_due, amount_paid, balance_owing, status, cancelled
from public.charters
where reserve_number::text = any(%s)
   or regexp_replace(reserve_number::text, '^0+', '') = any(%s)
order by regexp_replace(reserve_number::text, '^0+', ''), charter_id
''', (TARGET, list(TARGET_NORM)))
headers = cur.fetchall()

reserve_to_headers = defaultdict(list)
charter_ids = []
for r in headers:
    charter_id, reserve_number, *_ = r
    norm = reserve_number.lstrip('0')
    reserve_to_headers[norm].append(r)
    charter_ids.append(charter_id)

# 2) current charter_payments
cp_rows = []
if charter_ids:
    cur.execute('''
    select id, charter_id, payment_date, amount, payment_method, payment_key, payment_id, source
    from public.charter_payments
    where charter_id = any(%s)
    order by charter_id, payment_date nulls last, id
    ''', (charter_ids,))
    cp_rows = cur.fetchall()

cp_by_charter = defaultdict(list)
for r in cp_rows:
    cp_by_charter[r[1]].append(r)

# 3) payments rows
cur.execute('''
select reserve_number::text, payment_date, amount, payment_method, payment_id, payment_key, status
from public.payments
where reserve_number::text = any(%s)
   or regexp_replace(reserve_number::text, '^0+', '') = any(%s)
order by regexp_replace(reserve_number::text, '^0+', ''), payment_date nulls last, payment_id
''', (TARGET, list(TARGET_NORM)))
p_rows = cur.fetchall()

p_by_reserve = defaultdict(list)
for r in p_rows:
    p_by_reserve[r[0].lstrip('0')].append(r)

# 4) backup table rows
cur.execute("select to_regclass('public.backup_charter_payments_before_rebuild')")
backup_exists = cur.fetchone()[0] is not None
b_by_charter = defaultdict(list)
if backup_exists and charter_ids:
    cur.execute('''
    select id, charter_id, payment_date, amount, payment_method, payment_key, payment_id, source
    from public.backup_charter_payments_before_rebuild
    where charter_id = any(%s)
    order by charter_id, payment_date nulls last, id
    ''', (charter_ids,))
    for r in cur.fetchall():
        b_by_charter[r[1]].append(r)

for target in TARGET:
    norm = target.lstrip('0')
    print(f"\n=== RESERVE {target} ===")

    hdrs = reserve_to_headers.get(norm, [])
    if not hdrs:
        print("header: <none>")
    else:
        print("header:")
        for h in hdrs:
            charter_id, reserve_number, charter_date, total_due, amount_paid, balance_owing, status, cancelled = h
            print(f"  charter_id={charter_id} reserve_number={reserve_number} charter_date={charter_date} total_amount_due={total_due} amount_paid={amount_paid} balance_owing={balance_owing} status={status} cancelled={cancelled}")

    print("current charter_payments:")
    if not hdrs:
        print("  <none>")
    else:
        any_rows = False
        for h in hdrs:
            cid = h[0]
            rows = cp_by_charter.get(cid, [])
            if rows:
                any_rows = True
                print(f"  charter_id={cid}")
                for r in rows:
                    i, charter_id, payment_date, amount, method, pkey, pid, source = r
                    print(f"    id={i} payment_date={payment_date} amount={amount} payment_method={method} payment_key={pkey} payment_id={pid} source={source}")
        if not any_rows:
            print("  <none>")

    print("payments table:")
    prow = p_by_reserve.get(norm, [])
    if not prow:
        print("  <none>")
    else:
        for r in prow:
            reserve_number, payment_date, amount, method, pid, pkey, source = r
            print(f"  reserve_number={reserve_number} payment_date={payment_date} amount={amount} payment_method={method} payment_id={pid} payment_key={pkey} source={source}")

    print("backup_charter_payments_before_rebuild:")
    if not backup_exists:
        print("  <table not found>")
    elif not hdrs:
        print("  <none>")
    else:
        any_b = False
        for h in hdrs:
            cid = h[0]
            rows = b_by_charter.get(cid, [])
            if rows:
                any_b = True
                print(f"  charter_id={cid}")
                for r in rows:
                    i, charter_id, payment_date, amount, method, pkey, pid, source = r
                    print(f"    id={i} payment_date={payment_date} amount={amount} payment_method={method} payment_key={pkey} payment_id={pid} source={source}")
        if not any_b:
            print("  <none>")

cur.close(); conn.close()

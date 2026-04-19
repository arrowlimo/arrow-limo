import psycopg2
from collections import defaultdict

TARGET = ['012154','012574','013357']
TARGET_NORM = [t.lstrip('0') for t in TARGET]

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine', port=5432)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

cur.execute("""
select table_schema, table_name
from information_schema.tables
where table_schema='public'
  and table_name ilike 'backup%charter%payments%rebuild%'
order by table_name
""")
backup_tables = cur.fetchall()

cur.execute("""
select c.charter_id, c.reserve_number::text as reserve_number, c.charter_date,
       c.total_amount_due, c.amount_paid, c.balance_owing, c.status, c.cancelled
from public.charters c
where c.reserve_number::text = any(%s)
   or regexp_replace(c.reserve_number::text, '^0+', '') = any(%s)
order by regexp_replace(c.reserve_number::text, '^0+', ''), c.charter_id
""", (TARGET, TARGET_NORM))
charter_rows = cur.fetchall()

reserve_to_charters = defaultdict(list)
charter_ids_text = []
for row in charter_rows:
    cid, reserve_number, *_ = row
    reserve_to_charters[reserve_number.lstrip('0')].append(row)
    charter_ids_text.append(str(cid))

cp_by_reserve = defaultdict(list)
if charter_ids_text:
    cur.execute("""
    select c.reserve_number::text as reserve_number,
           cp.id, cp.charter_id, cp.payment_date, cp.amount, cp.payment_method, cp.payment_id, cp.payment_key, cp.source
    from public.charter_payments cp
    join public.charters c
      on cp.charter_id = c.charter_id::text
    where c.charter_id::text = any(%s)
    order by regexp_replace(c.reserve_number::text, '^0+', ''), cp.payment_date nulls last, cp.id
    """, (charter_ids_text,))
    for r in cur.fetchall():
        cp_by_reserve[r[0].lstrip('0')].append(r)

cur.execute("""
select p.reserve_number::text, p.payment_date, p.amount, p.payment_method, p.payment_id, p.payment_key,
       null::text as source
from public.payments p
where p.reserve_number::text = any(%s)
   or regexp_replace(p.reserve_number::text, '^0+', '') = any(%s)
order by regexp_replace(p.reserve_number::text, '^0+', ''), p.payment_date nulls last, p.payment_id
""", (TARGET, TARGET_NORM))
payments_by_reserve = defaultdict(list)
for r in cur.fetchall():
    payments_by_reserve[r[0].lstrip('0')].append(r)

backup_data = {}
for schema, table in backup_tables:
    table_key = f"{schema}.{table}"
    table_rows_by_reserve = defaultdict(list)
    if charter_ids_text:
        q = f"""
        select c.reserve_number::text as reserve_number,
               b.id, b.charter_id, b.payment_date, b.amount, b.payment_method, b.payment_id, b.payment_key, b.source
        from {schema}.{table} b
        join public.charters c
          on b.charter_id::text = c.charter_id::text
        where c.charter_id::text = any(%s)
        order by regexp_replace(c.reserve_number::text, '^0+', ''), b.payment_date nulls last, b.id
        """
        cur.execute(q, (charter_ids_text,))
        for r in cur.fetchall():
            table_rows_by_reserve[r[0].lstrip('0')].append(r)
    backup_data[table_key] = table_rows_by_reserve

lines = []
lines.append('=== DISCOVERED BACKUP TABLES ===')
if backup_tables:
    for s,t in backup_tables:
        lines.append(f'- {s}.{t}')
else:
    lines.append('<none>')

for target in TARGET:
    norm = target.lstrip('0')
    lines.append(f"\n================ RESERVE {target} ================")

    lines.append('--- charters ---')
    rows = reserve_to_charters.get(norm, [])
    if not rows:
        lines.append('  <none>')
    else:
        for h in rows:
            cid, reserve_number, charter_date, total_due, amount_paid, balance_owing, status, cancelled = h
            lines.append(f"  charter_id={cid} reserve_number={reserve_number} charter_date={charter_date} total_amount_due={total_due} amount_paid={amount_paid} balance_owing={balance_owing} status={status} cancelled={cancelled}")

    lines.append('--- current public.charter_payments (joined) ---')
    rows = cp_by_reserve.get(norm, [])
    if not rows:
        lines.append('  <none>')
    else:
        for r in rows:
            _, pid_row, cp_charter_id, payment_date, amount, method, payment_id, payment_key, source = r
            lines.append(f"  id={pid_row} charter_id={cp_charter_id} payment_date={payment_date} amount={amount} payment_method={method} payment_id={payment_id} payment_key={payment_key} source={source}")

    lines.append('--- public.payments ---')
    rows = payments_by_reserve.get(norm, [])
    if not rows:
        lines.append('  <none>')
    else:
        for r in rows:
            _, payment_date, amount, method, payment_id, payment_key, source = r
            lines.append(f"  payment_date={payment_date} amount={amount} payment_method={method} payment_id={payment_id} payment_key={payment_key} source={source}")

    for table_key, rows_by_reserve in backup_data.items():
        lines.append(f"--- {table_key} ---")
        rows = rows_by_reserve.get(norm, [])
        if not rows:
            lines.append('  <none>')
        else:
            for r in rows:
                _, bid, bcharter_id, payment_date, amount, method, payment_id, payment_key, source = r
                lines.append(f"  id={bid} charter_id={bcharter_id} payment_date={payment_date} amount={amount} payment_method={method} payment_id={payment_id} payment_key={payment_key} source={source}")

output='\n'.join(lines)
print(output)
with open('.tmp_reserve_audit_output.txt','w', encoding='utf-8') as f:
    f.write(output)

cur.close()
conn.close()

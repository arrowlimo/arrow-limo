import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

target = os.getenv("DB_TARGET", os.getenv("ALMS_DEFAULT_DB_TARGET", "neon"))
if str(target).lower().strip() == "local":
    params = dict(
        dbname=os.getenv("LOCAL_DB_NAME", "almsdata"),
        user=os.getenv("LOCAL_DB_USER", "postgres"),
        password=os.getenv("LOCAL_DB_PASSWORD", ""),
        sslmode=os.getenv("LOCAL_DB_SSLMODE", "prefer") or "prefer",
    )
    hosts = [os.getenv("LOCAL_DB_HOST", "localhost")]
else:
    params = dict(
        dbname=os.getenv("NEON_DB_NAME", os.getenv("DB_NAME", "neondb")),
        user=os.getenv("NEON_DB_USER", os.getenv("DB_USER", "")),
        password=os.getenv("NEON_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        sslmode=os.getenv("NEON_DB_SSLMODE", os.getenv("DB_SSLMODE", "require")) or "require",
    )
    hosts = [os.getenv("NEON_DB_HOST", os.getenv("DB_HOST", ""))]

conn = None
used_host = None
for host in hosts:
    try:
        c = psycopg2.connect(host=host, connect_timeout=5, **params)
        cur = c.cursor()
        cur.execute('select current_database(), current_user')
        print('CONNECTED', host, cur.fetchone())
        conn = c
        used_host = host
        break
    except Exception as e:
        print('FAILED', host, type(e).__name__, e)
if not conn:
    raise SystemExit('no host connected')
cur = conn.cursor()
cur.execute("""
select table_schema, table_name
from information_schema.columns
where column_name in (
  'charter_id','reserve_number','charter_date','driver_hours_worked','approved_hours',
  'driver_gratuity_amount','driver_gratuity','approved_gratuity','extra_gratuity','gratuity_percent'
)
group by table_schema, table_name
having count(distinct column_name) >= 8
order by table_schema, table_name
""")
print('TABLE_CANDIDATES')
for row in cur.fetchall():
    print(row)
cur.execute("""
select table_schema, table_name, column_name, data_type
from information_schema.columns
where table_schema='public' and table_name in ('employees','charters','reservations','trips','payroll','payroll_detail')
order by table_name, ordinal_position
""")
print('SELECTED_COLUMNS')
for row in cur.fetchall():
    print(row)
conn.close()

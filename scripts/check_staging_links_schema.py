import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='staging_driver_pay_links' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print('staging_driver_pay_links columns:')
for c in cols:
    print(f'  {c}')
cur.close()
conn.close()

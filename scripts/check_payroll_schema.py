import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'driver_payroll' ORDER BY ordinal_position")
print('driver_payroll columns:')
for r in cur.fetchall():
    print(f'  {r[0]} ({r[1]})')

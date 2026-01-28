import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('employee_pay_master columns:')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employee_pay_master' ORDER BY ordinal_position")
cols = []
for col in cur.fetchall():
    cname = col[0]
    print(f'  {cname}')
    cols.append(cname)

print('\nSample employee_pay_master data:')
cur.execute("SELECT * FROM employee_pay_master LIMIT 1")
row = cur.fetchone()
if row:
    for i, cname in enumerate(cols):
        print(f"  {cname}: {row[i]}")

print('\n\nemployee_pay_calc columns (first 20):')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employee_pay_calc' ORDER BY ordinal_position LIMIT 20")
for col in cur.fetchall():
    print(f"  {col[0]}")

print('\n\ndriver_payroll columns (first 15):')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='driver_payroll' ORDER BY ordinal_position LIMIT 15")
for col in cur.fetchall():
    print(f"  {col[0]}")

cur.close()
conn.close()

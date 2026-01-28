import psycopg2

c=psycopg2.connect(dbname='almsdata',user='postgres',host='localhost',password='***REMOVED***')
r=c.cursor()
r.execute('SELECT COUNT(*), SUM(COALESCE(gross_pay,0)), SUM(COALESCE(t4_box_14,0)), SUM(COALESCE(t4_box_22,0)) FROM driver_payroll WHERE year=2012')
row=r.fetchone()
print(f'2012 Records: {row[0]}')
print(f'Gross Pay Total: ${row[1]:,.2f}')
print(f'T4 Box 14 Total: ${row[2]:,.2f}')
print(f'T4 Box 22 Total: ${row[3]:,.2f}')

print('\nSample records:')
r.execute('SELECT employee_id, gross_pay, t4_box_14, t4_box_22, cpp, ei, tax FROM driver_payroll WHERE year=2012 LIMIT 10')
for row in r.fetchall():
    print(f'  EmpID: {row[0]}, Gross: ${row[1]}, T4-14: ${row[2]}, T4-22: ${row[3]}, CPP: ${row[4]}, EI: ${row[5]}, Tax: ${row[6]}')

c.close()

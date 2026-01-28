#!/usr/bin/env python3
import os, psycopg2

DB_HOST, DB_NAME, DB_USER, DB_PASSWORD = 'localhost', 'almsdata', 'postgres', '***REMOVED***'
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute('SELECT employee_pay_id, employee_id, gross_pay, cpp_employee, net_pay FROM employee_pay_master LIMIT 5')
print('Sample records after fix:')
print(f"{'ID':<8} {'Employee':<12} {'Gross':<15} {'CPP':<15} {'Net':<15}")
print('-'*65)
for row in cur.fetchall():
    pay_id, emp_id, gross, cpp, net = row
    print(f"{pay_id:<8} {emp_id:<12} ${gross:>12,.2f} ${cpp:>12,.2f} ${net:>12,.2f}")

cur.execute('SELECT SUM(cpp_employee) FROM employee_pay_master')
print(f"\nTotal CPP: ${cur.fetchone()[0]:,.2f}")

cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
print(f"Negative CPP records: {cur.fetchone()[0]}")

cur.close()
conn.close()

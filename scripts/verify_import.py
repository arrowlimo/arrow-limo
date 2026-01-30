#!/usr/bin/env python3
import os, psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Verify entry
cur.execute('SELECT driver_id, pay_date, gross_pay, cpp, ei, tax, net_pay FROM driver_payroll WHERE id = 18522')
row = cur.fetchone()
print(f'\n✓ Entry 18522 Verified:')
print(f'  Driver: {row[0]}, Date: {row[1]}')
print(f'  Gross: ${row[2]:.2f}, CPP: ${row[3]:.2f}, EI: ${row[4]:.2f}, Tax: ${row[5]:.2f}')
print(f'  Net: ${float(row[6]) if row[6] else 0:.2f}')

# 2012 totals
cur.execute("""
    SELECT COUNT(*), 
           ROUND(SUM(gross_pay)::numeric,2), 
           ROUND(SUM(cpp)::numeric,2), 
           ROUND(SUM(ei)::numeric,2), 
           ROUND(SUM(tax)::numeric,2) 
    FROM driver_payroll 
    WHERE pay_date >= '2012-01-01' AND pay_date < '2013-01-01' 
      AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)
""")
row = cur.fetchone()
print(f'\n2012 Payroll Totals (after import):')
print(f'  Entries:  {row[0]:>8,}')
print(f'  Gross:    ${float(row[1]):>14,.2f}')
print(f'  CPP:      ${float(row[2]):>14,.2f}')
print(f'  EI:       ${float(row[3]):>14,.2f}')
print(f'  Tax:      ${float(row[4]):>14,.2f}')

cur.close()
conn.close()

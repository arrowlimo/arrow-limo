#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('🔍 DEBUG PAYROLL QUERY FOR 2013')

cur.execute("""
    SELECT 
        COUNT(*) as entries,
        SUM(gross_pay) as total_gross,
        SUM(total_deductions) as total_deductions, 
        SUM(net_pay) as total_net,
        COUNT(DISTINCT driver_id) as unique_drivers,
        AVG(gross_pay) as avg_gross_per_entry,
        MIN(pay_date) as earliest_pay,
        MAX(pay_date) as latest_pay
    FROM driver_payroll 
    WHERE year = 2013
""")

payroll = cur.fetchone()
print(f'Payroll result type: {type(payroll)}')
print(f'Payroll result length: {len(payroll) if payroll else "None"}')
print(f'Payroll result: {payroll}')

if payroll:
    print('Attempting unpacking...')
    try:
        entries, gross, deductions, net, drivers, avg_gross, earliest, latest = payroll
        print('[OK] Unpacking successful')
        print(f'Entries: {entries}, Gross: {gross}, Net: {net}')
    except ValueError as e:
        print(f'[FAIL] Unpacking failed: {e}')

cur.close()
conn.close()
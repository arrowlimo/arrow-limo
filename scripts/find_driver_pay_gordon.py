#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

print('='*80)
print('SEARCHING DRIVER PAYROLL FOR: Gordon Deans')
print('='*80)

# driver_payroll table
print('\ndriver_payroll table:')
cur.execute("""
    SELECT id, driver_id, year, month, pay_date, gross_pay, net_pay, 
           employee_id, quickbooks_source
    FROM driver_payroll
    WHERE driver_id ILIKE %s
       OR driver_id ILIKE %s
    ORDER BY year, month
""", ('%gordon%', '%deans%'))

payroll = cur.fetchall()
if payroll:
    total_gross = 0
    total_net = 0
    for p in payroll:
        print(f"  ID {p[0]}: Driver '{p[1]}'")
        print(f"    {p[2]}-{p[3]:02d}, Pay Date: {p[4]}")
        print(f"    Gross: ${p[5]:.2f}, Net: ${p[6]:.2f}")
        print(f"    Employee ID: {p[7]}, Source: {p[8]}")
        print()
        total_gross += (p[5] or 0)
        total_net += (p[6] or 0)
    print(f"  TOTAL: Gross ${total_gross:,.2f}, Net ${total_net:,.2f}")
else:
    print("  No matches")

# Skip staging table if it doesn't exist
print('\n(staging_driver_pay table skipped - not present)')

# employees table
print('\nemployees table:')
cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name, 
           position, status, is_chauffeur
    FROM employees
    WHERE full_name ILIKE %s
       OR full_name ILIKE %s
       OR first_name ILIKE %s
       OR last_name ILIKE %s
    ORDER BY full_name
""", ('%gordon%', '%deans%', '%gordon%', '%deans%'))

employees = cur.fetchall()
if employees:
    for e in employees:
        print(f"  Employee ID: {e[0]}, Number: {e[1]}")
        print(f"    Name: {e[2]} (First: {e[3]}, Last: {e[4]})")
        print(f"    Position: {e[5]}, Status: {e[6]}, Chauffeur: {e[7]}")
        print()
else:
    print("  No matches")

# Check for Cal Red as well
print('\n' + '='*80)
print('ALSO CHECKING FOR: Cal Red')
print('='*80)

cur.execute("""
    SELECT id, driver_id, year, month, pay_date, gross_pay, net_pay
    FROM driver_payroll
    WHERE driver_id ILIKE %s
    ORDER BY year, month
""", ('%cal%red%',))

calred = cur.fetchall()
if calred:
    for p in calred:
        print(f"  ID {p[0]}: Driver '{p[1]}'")
        print(f"    {p[2]}-{p[3]:02d}, Pay Date: {p[4]}")
        print(f"    Gross: ${p[5]:.2f}, Net: ${p[6]:.2f}")
        print()
else:
    print("  No driver payroll matches for Cal Red")

cur.close()
conn.close()

#!/usr/bin/env python3
"""Verify Gordon Deans payroll entry against provided pay stub data."""
import os, psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

# Pay stub data to verify
EXPECTED = {
    'wages': 1025.00,
    'gratuities': 680.39,
    'expense_reimbursed': 108.72,
    'total_gross': 1814.11,
    'cpp': 69.98,
    'ei': 31.21,
    'fed_income_tax': 108.07,
    'total_deductions': 209.26,
    'net_pay': 1604.85,
    'vacation_available': 41.00,
    'reservations': ['007237', '007245', '007243', '007227', '007228', '007188', 
                     '007104', '007269', '007277', '007148', '007278', '007109', '007288']
}

conn = get_conn()
cur = conn.cursor()

# Search for Gordon Deans in employees
cur.execute("""
    SELECT employee_id, full_name, first_name, last_name 
    FROM employees 
    WHERE LOWER(full_name) LIKE '%gordon%' 
       OR LOWER(first_name) LIKE '%gordon%'
       OR LOWER(last_name) LIKE '%dean%'
""")

employees = cur.fetchall()
print(f"\n{'='*100}")
print(f"GORDON DEANS PAYROLL VERIFICATION")
print(f"{'='*100}\n")

if not employees:
    print("[FAIL] Gordon Deans not found in employees table")
    print("\nSearching by reservations instead...")
    
    # Search by reservations in charters
    reserve_list = ', '.join(f"'{r}'" for r in EXPECTED['reservations'])
    cur.execute(f"""
        SELECT DISTINCT driver_name, assigned_driver_id, employee_id
        FROM charters 
        WHERE reserve_number IN ({reserve_list})
    """)
    
    charter_drivers = cur.fetchall()
    if charter_drivers:
        print(f"\nDrivers found in charters for these reservations:")
        for row in charter_drivers:
            print(f"  Driver: {row[0]}, assigned_driver_id: {row[1]}, employee_id: {row[2]}")
        
        # Try to find payroll entries
        driver_ids = [str(row[1]) for row in charter_drivers if row[1]]
        employee_ids = [str(row[2]) for row in charter_drivers if row[2]]
        
        if driver_ids or employee_ids:
            conditions = []
            if driver_ids:
                driver_list = ', '.join(f"'{d}'" for d in driver_ids)
                conditions.append(f"driver_id IN ({driver_list})")
            if employee_ids:
                emp_list = ', '.join(employee_ids)
                conditions.append(f"employee_id IN ({emp_list})")
            
            where_clause = ' OR '.join(conditions)
            
            cur.execute(f"""
                SELECT id, driver_id, employee_id, pay_date, gross_pay, cpp, ei, tax,
                       net_pay, charter_id, reserve_number, source
                FROM driver_payroll 
                WHERE ({where_clause})
                  AND gross_pay BETWEEN 1700 AND 1900
                ORDER BY pay_date DESC
                LIMIT 10
            """)
            
            payroll_entries = cur.fetchall()
else:
    print(f"Found {len(employees)} employee(s) matching 'Gordon Deans':")
    for emp in employees:
        print(f"  ID: {emp[0]}, Name: {emp[1]}")
    
    # Search payroll by employee_id or driver_id
    emp_ids = [str(e[0]) for e in employees]
    
    cur.execute(f"""
        SELECT id, driver_id, employee_id, pay_date, gross_pay, cpp, ei, tax,
               net_pay, charter_id, reserve_number, source
        FROM driver_payroll 
        WHERE (employee_id IN ({', '.join(emp_ids)}) 
           OR driver_id IN ({', '.join(f"'{e}'" for e in emp_ids)}))
          AND gross_pay BETWEEN 1700 AND 1900
        ORDER BY pay_date DESC
        LIMIT 10
    """)
    
    payroll_entries = cur.fetchall()

if not payroll_entries:
    print("\n[FAIL] No payroll entries found matching expected gross pay range ($1700-$1900)")
else:
    print(f"\n{'='*100}")
    print(f"PAYROLL ENTRIES FOUND (gross pay $1700-$1900)")
    print(f"{'='*100}\n")
    
    for entry in payroll_entries:
        entry_id, driver_id, employee_id, pay_date, gross_pay, cpp, ei, tax, net_pay, charter_id, reserve_number, source = entry
        
        print(f"Entry ID: {entry_id}")
        print(f"Driver ID: {driver_id}, Employee ID: {employee_id}")
        print(f"Pay Date: {pay_date}")
        print(f"Source: {source}")
        print(f"Charter: {charter_id}, Reserve: {reserve_number}")
        
        print(f"\n{'Metric':<30} {'Expected':>15} {'Database':>15} {'Match':<10}")
        print(f"{'-'*80}")
        
        # Compare values
        gross_match = "✓" if abs(float(gross_pay or 0) - EXPECTED['total_gross']) < 0.01 else "[FAIL]"
        cpp_match = "✓" if abs(float(cpp or 0) - EXPECTED['cpp']) < 0.01 else "[FAIL]"
        ei_match = "✓" if abs(float(ei or 0) - EXPECTED['ei']) < 0.01 else "[FAIL]"
        tax_match = "✓" if abs(float(tax or 0) - EXPECTED['fed_income_tax']) < 0.01 else "[FAIL]"
        net_match = "✓" if net_pay and abs(float(net_pay) - EXPECTED['net_pay']) < 0.01 else "[FAIL]"
        
        print(f"{'Gross Pay':<30} ${EXPECTED['total_gross']:>14,.2f} ${float(gross_pay or 0):>14,.2f} {gross_match:<10}")
        print(f"{'CPP':<30} ${EXPECTED['cpp']:>14,.2f} ${float(cpp or 0):>14,.2f} {cpp_match:<10}")
        print(f"{'EI':<30} ${EXPECTED['ei']:>14,.2f} ${float(ei or 0):>14,.2f} {ei_match:<10}")
        print(f"{'Fed Income Tax':<30} ${EXPECTED['fed_income_tax']:>14,.2f} ${float(tax or 0):>14,.2f} {tax_match:<10}")
        print(f"{'Net Pay':<30} ${EXPECTED['net_pay']:>14,.2f} ${float(net_pay or 0):>14,.2f} {net_match:<10}")
        
        print(f"\n{'-'*100}\n")

# Check charters for the reservations
print(f"\n{'='*100}")
print(f"CHARTER VERIFICATION")
print(f"{'='*100}\n")

reserve_list = ', '.join(f"'{r}'" for r in EXPECTED['reservations'])
cur.execute(f"""
    SELECT reserve_number, charter_id, driver_name, assigned_driver_id, 
           charter_date, total_amount_due, paid_amount
    FROM charters 
    WHERE reserve_number IN ({reserve_list})
    ORDER BY reserve_number
""")

charters = cur.fetchall()
print(f"Found {len(charters)}/{len(EXPECTED['reservations'])} reservations in database:\n")

for charter in charters:
    print(f"  {charter[0]}: {charter[2] or 'No driver'} (Driver ID: {charter[3]}) - {charter[4]} - ${charter[5]:,.2f}")

missing = set(EXPECTED['reservations']) - set([c[0] for c in charters])
if missing:
    print(f"\n[WARN]  Missing reservations: {', '.join(sorted(missing))}")

cur.close()
conn.close()

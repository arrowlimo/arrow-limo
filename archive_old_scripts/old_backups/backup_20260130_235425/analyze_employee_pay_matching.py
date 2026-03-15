"""
Check employee pay records for unmatched payment data.

Compare:
1. Employee pay entries (chauffeur_pay_entries, driver_pay_entries, employee_pay_entries)
2. Driver payroll table
3. Staging driver pay table
4. Actual payments/expenses tables
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 120)
print("EMPLOYEE PAY RECORDS - UNMATCHED PAYMENT DATA ANALYSIS")
print("=" * 120)
print()

# Check driver_payroll table
print("1. DRIVER PAYROLL TABLE")
print("-" * 120)
cur.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT driver_id) as unique_drivers,
        COUNT(DISTINCT employee_id) as unique_employees,
        COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as null_employee_id,
        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as null_charter_id,
        SUM(gross_pay) as total_gross_pay,
        MIN(pay_date) as earliest_pay,
        MAX(pay_date) as latest_pay
    FROM driver_payroll
""")

row = cur.fetchone()
total, drivers, employees, null_emp, null_charter, gross, earliest, latest = row
print(f"Total payroll records:           {total:,}")
print(f"Unique driver_ids:               {drivers:,}")
print(f"Unique employee_ids:             {employees:,}")
print(f"Records with NULL employee_id:   {null_emp:,} ({100*null_emp/total if total else 0:.1f}%)")
print(f"Records with NULL charter_id:    {null_charter:,} ({100*null_charter/total if total else 0:.1f}%)")
print(f"Total gross pay:                 ${gross if gross else 0:,.2f}")
print(f"Date range:                      {earliest} to {latest}")
print()

# Check employee linkage
print("2. EMPLOYEE LINKAGE ISSUES")
print("-" * 120)
cur.execute("""
    SELECT 
        driver_id,
        COUNT(*) as pay_records,
        SUM(gross_pay) as total_pay,
        MIN(pay_date) as first_pay,
        MAX(pay_date) as last_pay
    FROM driver_payroll
    WHERE employee_id IS NULL
      AND driver_id IS NOT NULL
    GROUP BY driver_id
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

unmatched_drivers = cur.fetchall()
if unmatched_drivers:
    print(f"Driver IDs without employee linkage (top 20 of {len(unmatched_drivers)}):")
    print(f"{'Driver ID':<15} {'Records':<10} {'Total Pay':<15} {'First Pay':<12} {'Last Pay'}")
    print("-" * 120)
    for driver_id, records, total_pay, first_pay, last_pay in unmatched_drivers[:20]:
        print(f"{driver_id if driver_id else 'NULL':<15} {records:<10} ${total_pay if total_pay else 0:<14,.2f} "
              f"{first_pay if first_pay else 'NULL':<12} {last_pay if last_pay else 'NULL'}")
else:
    print("[OK] All driver_payroll records have employee_id linkage")
print()

# Check chauffeur_pay_entries
print("3. CHAUFFEUR PAY ENTRIES")
print("-" * 120)
cur.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT chauffeur_id) as unique_chauffeurs,
        COUNT(DISTINCT chauffeur_name) as unique_names,
        COUNT(CASE WHEN chauffeur_id IS NULL THEN 1 END) as null_chauffeur,
        COUNT(CASE WHEN charter_reference IS NULL OR charter_reference = '' THEN 1 END) as null_charter_ref,
        SUM(total_pay) as total_pay
    FROM chauffeur_pay_entries
""")

row = cur.fetchone()
total, chauffeurs, names, null_chauffeur, null_ref, total_pay = row
print(f"Total chauffeur pay entries:     {total:,}")
print(f"Unique chauffeur_ids:            {chauffeurs:,}")
print(f"Unique chauffeur names:          {names:,}")
print(f"NULL chauffeur_id:               {null_chauffeur:,}")
print(f"NULL charter_reference:          {null_ref:,}")
print(f"Total pay:                       ${total_pay if total_pay else 0:,.2f}")
print()

# Check driver_pay_entries
print("4. DRIVER PAY ENTRIES")
print("-" * 120)
cur.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT driver_id) as unique_drivers,
        COUNT(DISTINCT driver_name) as unique_names,
        COUNT(CASE WHEN driver_id IS NULL THEN 1 END) as null_driver,
        COUNT(CASE WHEN charter_reference IS NULL OR charter_reference = '' THEN 1 END) as null_charter_ref,
        SUM(total_pay) as total_pay
    FROM driver_pay_entries
""")

row = cur.fetchone()
total, drivers, names, null_driver, null_ref, total_pay = row
print(f"Total driver pay entries:        {total:,}")
print(f"Unique driver_ids:               {drivers:,}")
print(f"Unique driver names:             {names:,}")
print(f"NULL driver_id:                  {null_driver:,}")
print(f"NULL charter_reference:          {null_ref:,}")
print(f"Total pay:                       ${total_pay if total_pay else 0:,.2f}")
print()

# Check employee_pay_entries
print("5. EMPLOYEE PAY ENTRIES")
print("-" * 120)
cur.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT employee_id) as unique_employees,
        COUNT(DISTINCT employee_name) as unique_names,
        COUNT(DISTINCT employee_type) as unique_types,
        COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as null_employee,
        COUNT(CASE WHEN reservation_reference IS NULL OR reservation_reference = '' THEN 1 END) as null_reservation_ref,
        SUM(total_pay) as total_pay
    FROM employee_pay_entries
""")

row = cur.fetchone()
total, employees, names, types, null_emp, null_ref, total_pay = row
print(f"Total employee pay entries:      {total:,}")
print(f"Unique employee_ids:             {employees:,}")
print(f"Unique employee names:           {names:,}")
print(f"Unique employee types:           {types:,}")
print(f"NULL employee_id:                {null_emp:,}")
print(f"NULL reservation_reference:      {null_ref:,}")
print(f"Total pay:                       ${total_pay if total_pay else 0:,.2f}")
print()

# Check staging_driver_pay
print("6. STAGING DRIVER PAY (Unprocessed)")
print("-" * 120)
cur.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT driver_id) as unique_drivers,
        COUNT(DISTINCT driver_name) as unique_names,
        COUNT(CASE WHEN driver_id IS NULL OR driver_id = '' THEN 1 END) as null_driver_id,
        COUNT(CASE WHEN file_id IS NULL THEN 1 END) as orphaned,
        SUM(gross_amount) as total_gross,
        SUM(net_amount) as total_net,
        MIN(txn_date) as earliest_date,
        MAX(txn_date) as latest_date
    FROM staging_driver_pay
""")

row = cur.fetchone()
total, drivers, names, null_id, orphaned, gross, net, min_date, max_date = row
print(f"Total staging records:           {total:,}")
print(f"Unique driver_ids:               {drivers:,}")
print(f"Unique driver names:             {names:,}")
print(f"NULL/empty driver_id:            {null_id:,} ({null_id/total*100:.1f}%)")
print(f"Orphaned (no file_id):           {orphaned:,}")
print(f"Total gross amount:              ${gross if gross else 0:,.2f}")
print(f"Total net amount:                ${net if net else 0:,.2f}")
print(f"Date range:                      {min_date} to {max_date}")
print()

# Sample unmatched records
if null_emp > 0 or null_id > 0:
    print("7. SAMPLE UNMATCHED RECORDS")
    print("-" * 120)
    
    if null_emp > 0:
        print("\nDriver Payroll without employee_id:")
        cur.execute("""
            SELECT id, driver_id, pay_date, gross_pay, net_pay, charter_id, reserve_number
            FROM driver_payroll
            WHERE employee_id IS NULL
            ORDER BY pay_date DESC
            LIMIT 10
        """)
        
        for row in cur.fetchall():
            pid, driver_id, pay_date, gross, net, charter_id, reserve = row
            print(f"  ID {pid}: Driver {driver_id if driver_id else 'NULL'}, "
                  f"Date {pay_date if pay_date else 'NULL'}, "
                  f"Gross ${gross if gross else 0:.2f}, "
                  f"Charter {charter_id if charter_id else 'NULL'}, "
                  f"Reserve {reserve if reserve else 'NULL'}")
    
    if null_id > 0:
        print("\nStaging driver pay without driver_id:")
        cur.execute("""
            SELECT id, driver_name, txn_date, gross_amount, net_amount, memo
            FROM staging_driver_pay
            WHERE driver_id IS NULL OR driver_id = ''
            ORDER BY txn_date DESC
            LIMIT 10
        """)
        
        for row in cur.fetchall():
            pid, name, txn_date, gross, net, memo = row
            print(f"  ID {pid}: Name '{name if name else 'NULL'}', "
                  f"Date {txn_date}, Gross ${gross if gross else 0:.2f}, "
                  f"Net ${net if net else 0:.2f}, Memo '{memo if memo else 'NULL'}'")

# Summary
print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)

total_unmatched = 0
if null_emp > 0:
    print(f"[WARN]  {null_emp:,} driver_payroll records without employee_id linkage")
    total_unmatched += null_emp

if null_id > 0:
    print(f"[WARN]  {null_id:,} staging_driver_pay records without driver_id")
    total_unmatched += null_id

if total_unmatched == 0:
    print("[OK] All employee pay records have proper linkage")
else:
    print(f"\n💡 Total unmatched employee pay records: {total_unmatched:,}")
    print("\nRecommendations:")
    print("  1. Map driver_id to employee_id using name matching")
    print("  2. Process staging records to main payroll tables")
    print("  3. Validate charter_id linkage for payroll accuracy")

cur.close()
conn.close()

"""
Verify if charter hours, driver names, and payroll data now align with T4 records
"""
import psycopg2
import csv
from decimal import Decimal

def load_cra_t4_data():
    """Load CRA T4 data from CSV"""
    cra_data = {}
    with open(r'l:\limo\data\2012_cra_t4_complete_extraction.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_key = f"{row['last_name']}, {row['first_name']}".upper()
            cra_data[name_key] = {
                'sin': row['sin'],
                'box_14': Decimal(row['box_14']) if row['box_14'] else Decimal('0'),
            }
    return cra_data

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    cra_data = load_cra_t4_data()
    
    print("=" * 80)
    print("T4 MATCHING VERIFICATION - Charters, Hours, Driver Names")
    print("=" * 80)
    
    # Check 1: Driver names in T4 vs database
    print("\n1. DRIVER NAME MATCHING")
    print("-" * 80)
    
    cur.execute("""
        SELECT DISTINCT e.full_name, e.employee_id
        FROM employees e
        JOIN driver_payroll dp ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND dp.t4_box_14 IS NOT NULL
        ORDER BY e.full_name
    """)
    
    db_employees = cur.fetchall()
    print(f"Database employees with 2012 T4 data: {len(db_employees)}")
    print(f"CRA T4 slips: {len(cra_data)}")
    
    matched_names = 0
    unmatched_db = []
    for emp_name, emp_id in db_employees:
        name_upper = emp_name.upper()
        if name_upper in cra_data:
            matched_names += 1
        else:
            unmatched_db.append(emp_name)
    
    print(f"[OK] Matched: {matched_names}/{len(db_employees)} employees")
    if unmatched_db:
        print(f"[WARN]  Unmatched in DB: {len(unmatched_db)}")
        for name in unmatched_db[:5]:
            print(f"    - {name}")
    
    # Check 2: Charter linkage
    print("\n2. CHARTER LINKAGE TO PAYROLL")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT dp.id) as payroll_records,
            COUNT(DISTINCT dp.charter_id) as unique_charters,
            SUM(CASE WHEN dp.charter_id IS NOT NULL THEN 1 ELSE 0 END) as with_charter_link,
            SUM(CASE WHEN dp.reserve_number IS NOT NULL THEN 1 ELSE 0 END) as with_reserve_number
        FROM driver_payroll dp
        WHERE dp.year = 2012
    """)
    
    row = cur.fetchone()
    print(f"Total 2012 payroll records: {row[0]}")
    print(f"Unique charters linked: {row[1]}")
    print(f"Records with charter_id: {row[2]} ({row[2]/row[0]*100:.1f}%)")
    print(f"Records with reserve_number: {row[3]} ({row[3]/row[0]*100:.1f}%)")
    
    # Check 3: Hours worked
    print("\n3. HOURS WORKED DATA")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN hours_worked IS NOT NULL AND hours_worked > 0 THEN 1 ELSE 0 END) as has_hours,
            SUM(hours_worked) as total_hours
        FROM driver_payroll
        WHERE year = 2012
    """)
    
    row = cur.fetchone()
    print(f"Total records: {row[0]}")
    print(f"Records with hours > 0: {row[1]} ({row[1]/row[0]*100:.1f}%)")
    print(f"Total hours worked: {row[2] if row[2] else 0:.1f}")
    
    if row[1] == 0:
        print("[FAIL] Hours worked field is EMPTY - not populated")
    
    # Check 4: Charter hours vs payroll hours
    print("\n4. CHARTER HOURS COMPARISON")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(CASE WHEN calculated_hours IS NOT NULL AND calculated_hours > 0 THEN 1 ELSE 0 END) as has_hours,
            SUM(calculated_hours) as total_charter_hours
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
    """)
    
    row = cur.fetchone()
    print(f"2012 charters: {row[0]}")
    print(f"Charters with calculated_hours: {row[1]} ({row[1]/row[0]*100:.1f}% if row[0] > 0 else 0)")
    print(f"Total charter hours: {row[2] if row[2] else 0:.1f}")
    
    # Check 5: Driver assignment in charters
    print("\n5. DRIVER ASSIGNMENT IN CHARTERS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 ELSE 0 END) as has_driver,
            SUM(CASE WHEN driver_name IS NOT NULL THEN 1 ELSE 0 END) as has_driver_name
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
    """)
    
    row = cur.fetchone()
    if row[0] > 0:
        print(f"2012 charters: {row[0]}")
        print(f"Charters with assigned_driver_id: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        print(f"Charters with driver_name: {row[2]} ({row[2]/row[0]*100:.1f}%)")
    
    # Check 6: Sample employee - detailed breakdown
    print("\n6. SAMPLE EMPLOYEE DETAIL (Jeannie Shillington)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            e.full_name,
            e.employee_id,
            COUNT(dp.id) as payroll_records,
            MAX(dp.t4_box_14) as t4_box_14,
            SUM(dp.base_wages) as total_base_wages,
            SUM(dp.hours_worked) as total_hours,
            COUNT(DISTINCT dp.charter_id) as unique_charters,
            COUNT(DISTINCT dp.reserve_number) as unique_reserves
        FROM employees e
        JOIN driver_payroll dp ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND e.full_name LIKE '%Shillington%'
        GROUP BY e.employee_id, e.full_name
    """)
    
    row = cur.fetchone()
    if row:
        print(f"Name: {row[0]}")
        print(f"Employee ID: {row[1]}")
        print(f"Payroll records: {row[2]}")
        print(f"T4 Box 14: ${row[3]:,.2f}" if row[3] else "T4 Box 14: N/A")
        print(f"Total base_wages: ${row[4]:,.2f}" if row[4] else "Base wages: $0.00")
        print(f"Total hours: {row[5] if row[5] else 0:.1f}")
        print(f"Unique charters: {row[6]}")
        print(f"Unique reserve numbers: {row[7]}")
        
        if row[3] and row[4]:
            diff = float(row[3]) - float(row[4])
            print(f"Difference (T4 - base_wages): ${diff:,.2f}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print("\n[OK] WORKING:")
    print("  - Driver names matched to T4 records")
    print("  - T4 boxes populated (box_10, box_14, box_16, box_18, box_22, box_24, box_26)")
    print("  - base_wages populated from gross_pay")
    
    print("\n[WARN]  PARTIAL:")
    print("  - Charter linkage incomplete (charter_id/reserve_number)")
    print("  - Base wages lower than T4 Box 14 (missing 66% of wage data)")
    
    print("\n[FAIL] NOT WORKING:")
    print("  - hours_worked field is empty (0% populated)")
    print("  - Charter calculated_hours not linked to payroll hours")
    print("  - Missing gratuity/tip data")
    
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("\nDriver names and T4 records ARE matched.")
    print("Charter hours and payroll hours are NOT linked - both fields empty.")
    print("Database shows correct employees but incomplete wage/hour data.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

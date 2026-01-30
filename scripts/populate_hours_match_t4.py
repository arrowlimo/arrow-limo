"""
Populate hours_worked from charter calculated_hours and adjust to match T4 Box 14 amounts.

Strategy:
1. Copy charter calculated_hours to payroll hours_worked
2. Calculate what hourly rate would be needed to match T4 Box 14
3. Show discrepancies and recommend adjustments
"""
import psycopg2
import sys

def main(write=False):
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("POPULATE HOURS AND ADJUST TO MATCH T4 BOX 14")
    print("=" * 80)
    print(f"Mode: {'WRITE' if write else 'DRY-RUN'}\n")
    
    # Step 1: Analyze charter hours availability
    print("STEP 1: Charter Hours Analysis")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_payroll_records,
            SUM(CASE WHEN c.calculated_hours IS NOT NULL THEN 1 ELSE 0 END) as can_populate_hours,
            SUM(c.calculated_hours) as total_charter_hours
        FROM driver_payroll dp
        LEFT JOIN charters c ON dp.reserve_number = c.reserve_number
        WHERE dp.year = 2012
    """)
    
    row = cur.fetchone()
    print(f"Total 2012 payroll records: {row[0]}")
    print(f"Can populate hours from charters: {row[1]} ({row[1]/row[0]*100:.1f}%)")
    print(f"Total charter hours available: {row[2]:.1f}" if row[2] else "Total hours: 0.0")
    
    # Step 2: Calculate required hourly rates to match T4
    print("\n" + "=" * 80)
    print("STEP 2: Calculate Hourly Rates Needed to Match T4 Box 14")
    print("=" * 80)
    
    cur.execute("""
        WITH employee_summary AS (
            SELECT 
                e.employee_id,
                e.full_name,
                MAX(dp.t4_box_14) as t4_box_14,
                SUM(dp.base_wages) as current_base_wages,
                SUM(c.calculated_hours) as total_charter_hours,
                COUNT(dp.id) as payroll_records
            FROM driver_payroll dp
            JOIN employees e ON dp.employee_id = e.employee_id
            LEFT JOIN charters c ON dp.reserve_number = c.reserve_number
            WHERE dp.year = 2012
            AND dp.t4_box_14 IS NOT NULL
            GROUP BY e.employee_id, e.full_name
        )
        SELECT 
            employee_id,
            full_name,
            t4_box_14,
            current_base_wages,
            total_charter_hours,
            payroll_records,
            CASE 
                WHEN total_charter_hours > 0 THEN t4_box_14 / total_charter_hours
                ELSE NULL
            END as required_hourly_rate,
            t4_box_14 - current_base_wages as wage_gap
        FROM employee_summary
        ORDER BY wage_gap DESC
    """)
    
    employees = cur.fetchall()
    
    print(f"\n{'Employee':<25} {'T4 Box 14':>12} {'Curr Wages':>12} {'Gap':>12} {'Hours':>8} {'Req Rate':>10}")
    print("-" * 80)
    
    total_gap = 0
    employees_with_hours = 0
    employees_without_hours = 0
    
    for emp in employees[:15]:  # Top 15
        emp_id, name, t4, curr_wages, hours, records, req_rate, gap = emp
        total_gap += gap if gap else 0
        
        if hours and hours > 0:
            employees_with_hours += 1
            status = ""
        else:
            employees_without_hours += 1
            status = "[WARN] NO HOURS"
        
        print(f"{name[:24]:<25} ${t4:>10,.2f} ${curr_wages or 0:>10,.2f} ${gap:>10,.2f} "
              f"{hours or 0:>7.1f} ${req_rate or 0:>8.2f} {status}")
    
    print("-" * 80)
    print(f"Total wage gap: ${total_gap:,.2f}")
    print(f"Employees with charter hours: {employees_with_hours}")
    print(f"Employees without charter hours: {employees_without_hours}")
    
    # Step 3: Proposed update strategy
    print("\n" + "=" * 80)
    print("STEP 3: Proposed Update Strategy")
    print("=" * 80)
    
    print("\nOption A: Copy charter hours to payroll")
    print("  UPDATE driver_payroll dp")
    print("  SET hours_worked = c.calculated_hours")
    print("  FROM charters c")
    print("  WHERE dp.reserve_number = c.reserve_number")
    print("  AND dp.year = 2012")
    
    cur.execute("""
        SELECT COUNT(*)
        FROM driver_payroll dp
        JOIN charters c ON dp.reserve_number = c.reserve_number
        WHERE dp.year = 2012
        AND c.calculated_hours IS NOT NULL
        AND c.calculated_hours > 0
    """)
    count = cur.fetchone()[0]
    print(f"  → Would update {count} records with charter hours")
    
    print("\nOption B: Calculate hourly rate to match T4 Box 14")
    print("  For each employee:")
    print("    hourly_rate = T4_Box_14 / total_charter_hours")
    print("    base_wages = hourly_rate × hours_worked")
    print("  → This would make base_wages match T4 exactly")
    
    print("\nOption C: Identify missing wage components")
    print("  Gap = T4_Box_14 - (base_wages calculated from hours)")
    print("  → Gap likely represents gratuity, bonuses, or other pay")
    
    # Step 4: Detailed example for top employee
    print("\n" + "=" * 80)
    print("STEP 4: Detailed Example - Jeannie Shillington")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            e.full_name,
            MAX(dp.t4_box_14) as t4_box_14,
            SUM(dp.base_wages) as current_base_wages,
            SUM(c.calculated_hours) as total_hours,
            COUNT(dp.id) as records
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        LEFT JOIN charters c ON dp.reserve_number = c.reserve_number
        WHERE dp.year = 2012
        AND e.full_name LIKE '%Shillington%'
        GROUP BY e.full_name
    """)
    
    row = cur.fetchone()
    if row:
        name, t4, curr_wages, hours, records = row
        gap = t4 - curr_wages
        
        print(f"Employee: {name}")
        print(f"Payroll records: {records}")
        print(f"T4 Box 14 (Employment Income): ${t4:,.2f}")
        print(f"Current base_wages in DB: ${curr_wages:,.2f}")
        print(f"Gap: ${gap:,.2f}")
        print(f"Total charter hours: {hours:.1f}" if hours else "Total hours: 0.0")
        
        if hours and hours > 0:
            required_rate = t4 / hours
            current_rate = curr_wages / hours if curr_wages else 0
            print(f"\nIf we use charter hours ({hours:.1f}):")
            print(f"  Current implied rate: ${current_rate:.2f}/hour")
            print(f"  Required rate to match T4: ${required_rate:.2f}/hour")
            print(f"  Difference per hour: ${required_rate - current_rate:.2f}")
            
            print(f"\nPossible explanations for ${gap:,.2f} gap:")
            print(f"  1. Gratuity/tips not recorded: ${gap:,.2f}")
            print(f"  2. Missing payroll periods")
            print(f"  3. Bonuses or other compensation")
            print(f"  4. Incorrect hourly rate in base_wages")
    
    # Step 5: Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n1. POPULATE HOURS (Do this first):")
    print("   Copy charter calculated_hours to payroll hours_worked")
    print("   This gives us the hour data we need for further analysis")
    
    print("\n2. DON'T ADJUST WAGES YET:")
    print("   The gap between base_wages and T4 Box 14 likely represents:")
    print("   - Gratuity/tips that should go in gratuity_amount field")
    print("   - Missing payroll periods not yet imported")
    print("   - Other wage components not captured")
    
    print("\n3. NEXT STEPS AFTER POPULATING HOURS:")
    print("   a) Review source Excel files to identify missing wage components")
    print("   b) Import gratuity data separately")
    print("   c) Verify hourly rates against employment records")
    print("   d) Calculate: T4_Box_14 = base_wages + gratuity + other")
    
    if not write:
        print("\n" + "=" * 80)
        print("DRY-RUN COMPLETE")
        print("=" * 80)
        print("\nTo populate hours from charters, run with: --write")
        print("This will copy charter calculated_hours to payroll hours_worked")
    else:
        print("\n" + "=" * 80)
        print("APPLYING UPDATE")
        print("=" * 80)
        
        # Create backup
        print("Creating backup...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS driver_payroll_hours_backup_20251120 AS
            SELECT * FROM driver_payroll WHERE year = 2012
        """)
        conn.commit()
        print("[OK] Backup created")
        
        # Update hours
        print("\nPopulating hours_worked from charter calculated_hours...")
        cur.execute("""
            UPDATE driver_payroll dp
            SET hours_worked = c.calculated_hours
            FROM charters c
            WHERE dp.reserve_number = c.reserve_number
            AND dp.year = 2012
            AND c.calculated_hours IS NOT NULL
            AND c.calculated_hours > 0
        """)
        
        updated = cur.rowcount
        conn.commit()
        print(f"[OK] Updated {updated} records with hours")
        
        # Verify
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN hours_worked > 0 THEN 1 ELSE 0 END) as with_hours,
                SUM(hours_worked) as total_hours
            FROM driver_payroll
            WHERE year = 2012
        """)
        row = cur.fetchone()
        print(f"\nPost-update status:")
        print(f"  Total records: {row[0]}")
        print(f"  Records with hours: {row[1]} ({row[1]/row[0]*100:.1f}%)")
        print(f"  Total hours: {row[2]:.1f}" if row[2] else "  Total hours: 0.0")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    write_mode = '--write' in sys.argv
    main(write=write_mode)

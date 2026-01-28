"""
Fix 2012 driver_payroll records by populating base_wages from gross_pay
and identifying what other data components need to be sourced.
"""
import psycopg2
import sys

def main(write=False):
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("2012 PAYROLL DATA FIX - POPULATE MISSING FIELDS")
    print("=" * 80)
    print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    
    # Step 1: Analyze current state
    print("\n" + "-" * 80)
    print("CURRENT STATE ANALYSIS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN base_wages IS NULL OR base_wages = 0 THEN 1 ELSE 0 END) as empty_base_wages,
            SUM(CASE WHEN gratuity_amount IS NULL OR gratuity_amount = 0 THEN 1 ELSE 0 END) as empty_gratuity,
            SUM(CASE WHEN hours_worked IS NULL OR hours_worked = 0 THEN 1 ELSE 0 END) as empty_hours,
            SUM(gross_pay) as total_gross,
            SUM(expenses) as total_expenses
        FROM driver_payroll
        WHERE year = 2012
    """)
    row = cur.fetchone()
    
    print(f"Total 2012 records: {row[0]}")
    print(f"Records with empty/zero base_wages: {row[1]} ({row[1]/row[0]*100:.1f}%)")
    print(f"Records with empty/zero gratuity: {row[2]} ({row[2]/row[0]*100:.1f}%)")
    print(f"Records with empty/zero hours: {row[3]} ({row[3]/row[0]*100:.1f}%)")
    print(f"Current total gross_pay: ${row[4]:,.2f}" if row[4] else "Current total gross_pay: $0.00")
    print(f"Current total expenses: ${row[5]:,.2f}" if row[5] else "Current total expenses: $0.00")
    
    # Step 2: Proposed fix - populate base_wages from gross_pay
    print("\n" + "-" * 80)
    print("PROPOSED FIX #1: Populate base_wages from gross_pay")
    print("-" * 80)
    print("Logic: WHERE base_wages IS NULL OR base_wages = 0")
    print("       SET base_wages = gross_pay")
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_pay)
        FROM driver_payroll
        WHERE year = 2012
        AND (base_wages IS NULL OR base_wages = 0)
        AND gross_pay IS NOT NULL AND gross_pay > 0
    """)
    row = cur.fetchone()
    print(f"\nWould update {row[0]} records")
    print(f"Total value to populate: ${row[1]:,.2f}" if row[1] else "Total: $0.00")
    
    if write:
        print("\nApplying update...")
        cur.execute("""
            UPDATE driver_payroll
            SET base_wages = gross_pay
            WHERE year = 2012
            AND (base_wages IS NULL OR base_wages = 0)
            AND gross_pay IS NOT NULL AND gross_pay > 0
        """)
        updated = cur.rowcount
        print(f"[OK] Updated {updated} records")
        conn.commit()
    
    # Step 3: Analyze what remains
    print("\n" + "-" * 80)
    print("REMAINING DATA GAPS")
    print("-" * 80)
    
    # Check if expenses field actually contains wages
    cur.execute("""
        SELECT 
            e.full_name,
            COUNT(*) as records,
            SUM(dp.gross_pay) as total_gross,
            SUM(dp.expenses) as total_expenses,
            SUM(dp.gratuity_amount) as total_gratuity
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        GROUP BY e.full_name
        HAVING SUM(dp.expenses) > SUM(dp.gross_pay)
        ORDER BY SUM(dp.expenses) DESC
        LIMIT 5
    """)
    
    expense_heavy = cur.fetchall()
    if expense_heavy:
        print("\nEmployees where expenses > gross_pay (possible data entry issue):")
        for emp in expense_heavy:
            print(f"  {emp[0]}: gross=${emp[2]:,.2f}, expenses=${emp[3]:,.2f}")
        print("\n[WARN]  This suggests 'expenses' field may contain wage data, not just expense reimbursements")
    
    # Step 4: Calculate what's still missing to match T4
    print("\n" + "-" * 80)
    print("REMAINING DISCREPANCY TO T4 BOX 14")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            SUM(t4_box_14) as cra_total,
            SUM(gross_pay) as db_gross,
            SUM(base_wages) as db_base_wages
        FROM driver_payroll
        WHERE year = 2012
        AND t4_box_14 IS NOT NULL
    """)
    row = cur.fetchone()
    
    # Note: t4_box_14 is populated on EVERY record for employees with T4s
    # This creates inflated sums. We need to group by employee first.
    cur.execute("""
        SELECT 
            e.full_name,
            MAX(dp.t4_box_14) as cra_box_14,
            SUM(dp.gross_pay) as db_gross
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND dp.t4_box_14 IS NOT NULL
        GROUP BY e.employee_id, e.full_name
        HAVING MAX(dp.t4_box_14) > SUM(dp.gross_pay)
        ORDER BY (MAX(dp.t4_box_14) - SUM(dp.gross_pay)) DESC
    """)
    
    discrepancies = cur.fetchall()
    print(f"\nEmployees still short of T4 Box 14: {len(discrepancies)}")
    
    total_missing = sum(d[1] - d[2] for d in discrepancies)
    print(f"Total still missing: ${total_missing:,.2f}")
    
    print("\nTop 5 largest gaps:")
    for emp in discrepancies[:5]:
        missing = emp[1] - emp[2]
        print(f"  {emp[0]}: CRA ${emp[1]:,.2f} - DB ${emp[2]:,.2f} = ${missing:,.2f} short")
    
    # Step 5: Recommendations
    print("\n" + "=" * 80)
    print("FINDINGS & RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n1. IMMEDIATE FIX APPLIED (if --write):")
    print("   [OK] Populate base_wages from gross_pay for empty records")
    
    print("\n2. DATA SOURCE ISSUES:")
    print("   [WARN]  'expenses' field may contain wage data, not expense reimbursements")
    print("   [WARN]  Database has incomplete payroll records for 2012")
    print("   [WARN]  Missing ~${:,.2f} in wages to match T4 Box 14".format(total_missing))
    
    print("\n3. NEXT STEPS:")
    print("   a) Review source data files for 2012 payroll:")
    print("      - Check Excel files in L:\\limo\\payroll\\ or similar")
    print("      - Look for QuickBooks payroll exports")
    print("      - Check for PDF payroll reports")
    print("   b) Determine if 'expenses' field should be renamed/split:")
    print("      - If expenses contain wages, add to base_wages")
    print("      - Create separate expense_reimbursement field if needed")
    print("   c) Import gratuity/tip data if tracked separately")
    print("   d) Import hours_worked data if available")
    
    print("\n4. T4 BOX CALCULATION:")
    print("   Box 14 should equal: base_wages + gratuity_amount + taxable_benefits")
    print("   (NOT including expense reimbursements)")
    
    if not write:
        print("\n" + "=" * 80)
        print("Run with --write flag to apply changes")
        print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    write_mode = '--write' in sys.argv
    main(write=write_mode)

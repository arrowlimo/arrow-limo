#!/usr/bin/env python3
"""
Check if monthly driver_payroll records match with T4 records.

Compare:
1. T4 Box 14 values in driver_payroll vs actual T4 slips
2. Annual totals from monthly payroll vs T4 submissions
3. Identify discrepancies
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def check_payroll_t4_match():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("PAYROLL vs T4 RECORDS RECONCILIATION")
    print("=" * 80)
    
    # 1. Check if t4_slips table exists
    print("\n1. CHECKING FOR T4_SLIPS TABLE:")
    print("-" * 80)
    
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 't4_slips'
        )
    """)
    t4_table_exists = cur.fetchone()['exists']
    
    if t4_table_exists:
        cur.execute("SELECT COUNT(*) as count FROM t4_slips")
        t4_count = cur.fetchone()['count']
        print(f"[OK] t4_slips table exists with {t4_count} records")
        
        if t4_count > 0:
            cur.execute("""
                SELECT tax_year, COUNT(*) as employees,
                       SUM(box_14_employment_income) as total_income
                FROM t4_slips
                GROUP BY tax_year
                ORDER BY tax_year
            """)
            t4_summary = cur.fetchall()
            
            print("\nT4 SLIPS SUMMARY BY YEAR:")
            for row in t4_summary:
                print(f"  {row['tax_year']}: {row['employees']} employees, "
                      f"${row['total_income']:,.2f} total income")
    else:
        print("[FAIL] t4_slips table does NOT exist")
        print("\n   This means T4 data is only stored in driver_payroll.t4_box_14 column")
    
    # 2. Check driver_payroll T4 Box 14 values
    print("\n\n2. DRIVER_PAYROLL T4 BOX 14 ANALYSIS:")
    print("-" * 80)
    
    cur.execute("""
        SELECT year,
               COUNT(*) as total_entries,
               COUNT(DISTINCT employee_id) as unique_employees,
               SUM(gross_pay) as total_gross,
               SUM(t4_box_14) as total_t4_income,
               SUM(CASE WHEN t4_box_14 > 0 THEN 1 ELSE 0 END) as entries_with_t4,
               SUM(CASE WHEN t4_box_14 IS NULL OR t4_box_14 = 0 THEN 1 ELSE 0 END) as entries_without_t4
        FROM driver_payroll
        GROUP BY year
        ORDER BY year
    """)
    payroll_summary = cur.fetchall()
    
    print(f"\n{'Year':<6} {'Entries':<8} {'Employees':<10} {'Gross Pay':<14} "
          f"{'T4 Box 14':<14} {'With T4':<8} {'No T4':<8} {'Match?':<10}")
    print("-" * 95)
    
    for row in payroll_summary:
        gross = float(row['total_gross'] or 0)
        t4 = float(row['total_t4_income'] or 0)
        
        if t4 == 0:
            match_status = "[FAIL] NO T4"
        elif abs(gross - t4) < 0.01:
            match_status = "[OK] MATCH"
        else:
            diff = gross - t4
            match_status = f"[WARN]  ${diff:,.2f}"
        
        print(f"{row['year']:<6} {row['total_entries']:<8} {row['unique_employees']:<10} "
              f"${gross:>12,.2f} ${t4:>12,.2f} {row['entries_with_t4']:<8} "
              f"{row['entries_without_t4']:<8} {match_status:<10}")
    
    # 3. Check for any non-zero T4 Box 14 values
    print("\n\n3. CHECKING FOR NON-ZERO T4 BOX 14 VALUES:")
    print("-" * 80)
    
    cur.execute("""
        SELECT year, COUNT(*) as count, 
               SUM(t4_box_14) as total,
               COUNT(DISTINCT employee_id) as employees
        FROM driver_payroll
        WHERE t4_box_14 > 0
        GROUP BY year
        ORDER BY year
    """)
    nonzero_t4 = cur.fetchall()
    
    if nonzero_t4:
        print(f"Found {len(nonzero_t4)} years with non-zero T4 Box 14 values:")
        for row in nonzero_t4:
            print(f"  {row['year']}: {row['count']} entries, "
                  f"{row['employees']} employees, ${row['total']:,.2f} total")
    else:
        print("[FAIL] NO non-zero T4 Box 14 values found in driver_payroll")
        print("   All t4_box_14 values are NULL or 0")
    
    # 4. Check other T4 box columns
    print("\n\n4. CHECKING OTHER T4 BOX COLUMNS:")
    print("-" * 80)
    
    t4_boxes = ['t4_box_14', 't4_box_16', 't4_box_18', 't4_box_22', 
                't4_box_24', 't4_box_26', 't4_box_44', 't4_box_46', 't4_box_52']
    
    for box in t4_boxes:
        cur.execute(f"""
            SELECT COUNT(*) as count, SUM({box}) as total
            FROM driver_payroll
            WHERE {box} > 0
        """)
        result = cur.fetchone()
        
        if result['count'] > 0:
            print(f"  {box}: {result['count']} non-zero entries, "
                  f"total: ${result['total']:,.2f}")
        else:
            print(f"  {box}: ALL zeros or NULL")
    
    # 5. Summary and recommendations
    print("\n\n" + "=" * 80)
    print("ANALYSIS SUMMARY:")
    print("=" * 80)
    
    total_years = len(payroll_summary)
    total_gross = sum(float(row['total_gross'] or 0) for row in payroll_summary)
    total_t4 = sum(float(row['total_t4_income'] or 0) for row in payroll_summary)
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Years with payroll data: {total_years}")
    print(f"   Total gross pay: ${total_gross:,.2f}")
    print(f"   Total T4 Box 14 income: ${total_t4:,.2f}")
    
    if total_t4 == 0:
        print(f"\n[FAIL] CRITICAL FINDING:")
        print(f"   NO T4 income has been recorded in driver_payroll")
        print(f"   All t4_box_14 values are 0 or NULL")
        print(f"\n   This means:")
        print(f"   • driver_payroll contains monthly pay records")
        print(f"   • BUT T4 Box 14 column was never populated")
        print(f"   • Either:")
        print(f"     a) No T4s were ever filed (pay below basic personal amount)")
        print(f"     b) T4s were filed but not recorded in this database")
        print(f"     c) T4 data is stored elsewhere (QuickBooks, paper files)")
    else:
        print(f"\n[OK] T4 DATA EXISTS:")
        print(f"   ${total_t4:,.2f} in T4 income recorded")
        
        if abs(total_gross - total_t4) < 1.00:
            print(f"   [OK] Matches gross pay (difference: ${abs(total_gross - total_t4):.2f})")
        else:
            diff = total_gross - total_t4
            print(f"   [WARN]  DISCREPANCY: ${abs(diff):,.2f} difference from gross pay")
    
    print(f"\n💡 RECOMMENDATIONS:")
    if total_t4 == 0:
        print(f"   1. Check if employees had income below basic personal amount")
        print(f"   2. Verify if T4s were actually filed with CRA")
        print(f"   3. If T4s exist, import T4 data into driver_payroll.t4_box_* columns")
        print(f"   4. Consider creating separate t4_slips table for official T4 records")
    
    if not t4_table_exists:
        print(f"   5. Create t4_slips table to track official CRA submissions")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_payroll_t4_match()

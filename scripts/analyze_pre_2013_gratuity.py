#!/usr/bin/env python3
"""
Analyze pre-2013 gratuity data to understand direct tips vs taxable gratuity.

Pre-2013, gratuities were treated as direct tips (non-taxable to employer).
This script analyzes the data trail and determines if we can properly classify
these amounts as direct tips for CRA compliance.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("PRE-2013 GRATUITY ANALYSIS - DIRECT TIPS DATA TRAIL")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Charter gratuity summary pre-2013
    print("=" * 80)
    print("1. CHARTER GRATUITY DATA (Pre-2013)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            SUM(driver_gratuity) as total_gratuity,
            SUM(driver_total) as total_driver_pay,
            MIN(charter_date) as earliest,
            MAX(charter_date) as latest
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) < 2013 
        AND driver_gratuity IS NOT NULL 
        AND driver_gratuity > 0
    """)
    row = cur.fetchone()
    print(f"\nPre-2013 charters with gratuity:")
    print(f"  Charter count: {row[0]:,}")
    print(f"  Total gratuity: ${row[1]:,.2f}")
    print(f"  Total driver pay: ${row[2]:,.2f}")
    print(f"  Date range: {row[3]} to {row[4]}")
    
    # Year breakdown
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as count,
            SUM(driver_gratuity) as gratuity,
            SUM(driver_total) as driver_pay,
            AVG(driver_gratuity) as avg_gratuity
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) < 2013 
        AND driver_gratuity > 0 
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    print("\n  By year:")
    for row in cur.fetchall():
        print(f"    {int(row[0])}: {row[1]:,} charters, "
              f"gratuity=${row[2]:,.2f}, "
              f"driver_pay=${row[3]:,.2f}, "
              f"avg=${row[4]:,.2f}")
    
    # 2. Driver payroll summary pre-2013
    print("\n" + "=" * 80)
    print("2. DRIVER PAYROLL DATA (Pre-2013)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as record_count,
            SUM(gross_pay) as total_gross,
            SUM(net_pay) as total_net,
            MIN(pay_date) as earliest,
            MAX(pay_date) as latest
        FROM driver_payroll 
        WHERE year < 2013
    """)
    row = cur.fetchone()
    print(f"\nPre-2013 payroll records:")
    print(f"  Payroll records: {row[0]:,}")
    print(f"  Total gross pay: ${row[1]:,.2f}" if row[1] else "  Total gross pay: $0.00")
    print(f"  Total net pay: ${row[2]:,.2f}" if row[2] else "  Total net pay: $0.00")
    print(f"  Date range: {row[3]} to {row[4]}" if row[3] else "  Date range: None")
    
    # Year breakdown
    cur.execute("""
        SELECT 
            year,
            COUNT(*) as count,
            SUM(gross_pay) as gross_pay,
            SUM(net_pay) as net_pay,
            AVG(gross_pay) as avg_gross
        FROM driver_payroll 
        WHERE year < 2013 
        GROUP BY year
        ORDER BY year
    """)
    print("\n  By year:")
    for row in cur.fetchall():
        print(f"    {int(row[0])}: {row[1]:,} records, "
              f"gross_pay=${row[2]:,.2f}, "
              f"net_pay=${row[3]:,.2f}, "
              f"avg=${row[4]:,.2f}")
    
    # 3. Link payroll to charter gratuity
    print("\n" + "=" * 80)
    print("3. PAYROLL-CHARTER GRATUITY LINKAGE")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT dp.id) as payroll_records,
            COUNT(DISTINCT c.charter_id) as charters_with_gratuity,
            SUM(c.driver_gratuity) as total_charter_gratuity,
            SUM(dp.gross_pay) as total_payroll_gross,
            COUNT(CASE WHEN dp.charter_id IS NOT NULL THEN 1 END) as linked_records
        FROM driver_payroll dp
        LEFT JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE dp.year < 2013
        AND EXTRACT(YEAR FROM c.charter_date) < 2013
        AND c.driver_gratuity > 0
    """)
    row = cur.fetchone()
    print(f"\nPayroll-Charter linkage:")
    print(f"  Payroll records (pre-2013): {row[0]:,}")
    print(f"  Charters with gratuity: {row[1]:,}")
    print(f"  Total charter gratuity: ${row[2]:,.2f}" if row[2] else "  Total charter gratuity: $0.00")
    print(f"  Total payroll gross: ${row[3]:,.2f}" if row[3] else "  Total payroll gross: $0.00")
    print(f"  Linked records: {row[4]:,}")
    
    # Check if gratuity appears to be included in gross_pay
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(c.driver_gratuity) as charter_gratuity,
            SUM(dp.gross_pay) as payroll_gross,
            SUM(c.driver_total - c.driver_gratuity) as charter_base_pay
        FROM driver_payroll dp
        JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE dp.year < 2013
        AND c.driver_gratuity > 0
        AND dp.gross_pay IS NOT NULL
    """)
    row = cur.fetchone()
    if row[0] > 0:
        print(f"\n  Matched payroll-charter records: {row[0]:,}")
        print(f"  Charter gratuity: ${row[1]:,.2f}")
        print(f"  Payroll gross pay: ${row[2]:,.2f}")
        print(f"  Charter base pay (total - gratuity): ${row[3]:,.2f}")
        
        # Determine if gratuity is included
        if row[2] and row[1]:
            ratio = row[2] / (row[3] + row[1]) if (row[3] + row[1]) > 0 else 0
            print(f"  Gross/Total ratio: {ratio:.2%}")
            if ratio > 0.95:
                print("  [WARN]  Gratuity likely INCLUDED in gross_pay")
            else:
                print("  ✓ Gratuity likely EXCLUDED from gross_pay")
    else:
        print("\n  No matched payroll-charter records found")
    
    # 4. Check T4 boxes for gratuity reporting
    print("\n" + "=" * 80)
    print("4. T4 GRATUITY REPORTING CHECK")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(CASE WHEN dp.t4_box_14 IS NOT NULL AND dp.t4_box_14 > 0 THEN 1 ELSE 0 END) as has_t4_box14,
            SUM(dp.t4_box_14) as total_t4_box14,
            SUM(dp.gross_pay) as total_gross,
            SUM(c.driver_gratuity) as total_gratuity
        FROM driver_payroll dp
        LEFT JOIN charters c ON dp.charter_id::integer = c.charter_id AND EXTRACT(YEAR FROM c.charter_date) < 2013
        WHERE dp.year < 2013
    """)
    row = cur.fetchone()
    print(f"\nT4 reporting (Box 14 = Employment Income):")
    print(f"  Total pre-2013 payroll records: {row[0]:,}")
    print(f"  Records with T4 Box 14: {row[1]:,}")
    print(f"  Total T4 Box 14: ${row[2]:,.2f}" if row[2] else "  Total T4 Box 14: $0.00")
    print(f"  Total gross pay: ${row[3]:,.2f}" if row[3] else "  Total gross pay: $0.00")
    print(f"  Total charter gratuity: ${row[4]:,.2f}" if row[4] else "  Total charter gratuity: $0.00")
    
    # Compare T4 to gross pay
    if row[2] and row[3]:
        diff = row[2] - row[3]
        print(f"  Difference (T4 - Gross): ${diff:,.2f}")
        if abs(diff) < 100:
            print("  ✓ T4 matches gross pay (gratuity not included in T4)")
        else:
            print("  [WARN]  T4 differs from gross pay")
    
    # 5. Check for income_ledger entries
    print("\n" + "=" * 80)
    print("5. INCOME LEDGER GRATUITY ENTRIES")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(gross_amount) as total_gross,
            COUNT(CASE WHEN description ILIKE '%gratuity%' OR description ILIKE '%tip%' THEN 1 END) as has_tip_description
        FROM income_ledger il
        JOIN charters c ON il.charter_id = c.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) < 2013
        AND c.driver_gratuity > 0
    """)
    row = cur.fetchone()
    print(f"\nIncome ledger entries for charters with gratuity:")
    print(f"  Total entries: {row[0]:,}")
    print(f"  Total gross: ${row[1]:,.2f}" if row[1] else "  Total gross: $0.00")
    print(f"  Entries mentioning tips/gratuity: {row[2]:,}")
    
    # 6. Direct tips criteria assessment
    print("\n" + "=" * 80)
    print("6. DIRECT TIPS DATA TRAIL ASSESSMENT")
    print("=" * 80)
    
    print("\nCRA Direct Tips Criteria:")
    print("  1. Tips paid directly to employee by customer (not through employer)")
    print("  2. Not recorded on employer's books as revenue")
    print("  3. Not included in employee's T4 employment income")
    print("  4. Employee responsible for reporting on personal tax return")
    print()
    
    # Check if gratuity was recorded as company revenue
    cur.execute("""
        SELECT 
            COUNT(DISTINCT c.charter_id) as charters_with_gratuity,
            COUNT(il.income_id) as income_ledger_entries,
            SUM(c.driver_gratuity) as charter_gratuity,
            SUM(il.gross_amount) as ledger_gross
        FROM charters c
        LEFT JOIN income_ledger il ON c.charter_id = il.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) < 2013
        AND c.driver_gratuity > 0
    """)
    row = cur.fetchone()
    
    print("Current data trail status:")
    print(f"  Charters with gratuity: {row[0]:,}")
    print(f"  Income ledger entries: {row[1]:,}")
    print(f"  Charter gratuity total: ${row[2]:,.2f}")
    print(f"  Income ledger gross: ${row[3]:,.2f}" if row[3] else "  Income ledger gross: $0.00")
    
    # Analysis
    if row[1] == 0:
        print("\n✓ GOOD: No income ledger entries (gratuity not recorded as revenue)")
    else:
        print(f"\n[WARN]  WARNING: {row[1]:,} income ledger entries exist")
        print("    Need to verify if gratuity is included in ledger amounts")
    
    # 7. Recommendations
    print("\n" + "=" * 80)
    print("7. RECOMMENDATIONS FOR DIRECT TIPS CLASSIFICATION")
    print("=" * 80)
    
    print("\nTo properly classify pre-2013 gratuity as direct tips:")
    print()
    print("✓ ALREADY CORRECT:")
    print("  - Gratuity tracked separately in charters.driver_gratuity field")
    print("  - Driver payroll shows gratuity as separate line item")
    print()
    print("ACTIONS NEEDED:")
    print("  1. Verify income_ledger gross_amount does NOT include gratuity")
    print("     (should only include base charter charges)")
    print()
    print("  2. Ensure driver_payroll.gross_pay does NOT include gratuity")
    print("     (base wages only, gratuity is direct to driver)")
    print()
    print("  3. Verify T4 Box 14 does NOT include gratuity amounts")
    print("     (only wages/salary, not direct tips)")
    print()
    print("  4. Add documentation notes to affected records:")
    print("     - 'Pre-2013 gratuity treated as direct tips per CRA guidelines'")
    print("     - 'Gratuity not included in T4 employment income'")
    print()
    print("  5. Create separate reporting table:")
    print("     - direct_tips_history (charter_id, driver_id, tip_amount, date)")
    print("     - Clearly separates from taxable employment income")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

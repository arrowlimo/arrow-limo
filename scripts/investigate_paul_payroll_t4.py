#!/usr/bin/env python3
"""
Investigate Paul D Richard's payroll and T4 records.

Check:
1. Employee records (salary vs wages)
2. T4 records submitted to CRA
3. Driver payroll entries
4. Payment patterns 2012-2025
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def investigate_paul_records():
    """Investigate Paul D Richard's payroll and T4 situation."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("PAUL D RICHARD - PAYROLL & T4 INVESTIGATION")
    print("=" * 80)
    
    # 1. Get all Paul D Richard employee records
    print("\n1. PAUL'S EMPLOYEE RECORDS:")
    print("-" * 80)
    cur.execute("""
        SELECT employee_id, employee_number, full_name, position, 
               hire_date, employment_status, status, 
               hourly_rate, salary, is_chauffeur,
               t4_sin, created_at, updated_at
        FROM employees 
        WHERE LOWER(full_name) LIKE '%paul%richard%'
           OR LOWER(full_name) LIKE '%paul d%'
        ORDER BY employee_id
    """)
    paul_records = cur.fetchall()
    
    for rec in paul_records:
        print(f"\nID {rec['employee_id']}: {rec['full_name']}")
        print(f"  Emp#: {rec['employee_number']}")
        print(f"  Position: {rec['position']}")
        print(f"  Hired: {rec['hire_date']} | Employment Status: {rec['employment_status']} | Status: {rec['status']}")
        print(f"  SIN: {rec['t4_sin']}")
        print(f"  Hourly Rate: ${rec['hourly_rate']} | Salary: ${rec['salary']}")
        print(f"  Is Chauffeur: {rec['is_chauffeur']}")
        print(f"  Created: {rec['created_at']}")
    
    # 2. Check T4 records for Paul
    print("\n\n2. PAUL'S T4 RECORDS (CRA SUBMISSIONS):")
    print("-" * 80)
    
    # Check if t4_slips table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 't4_slips'
        )
    """)
    t4_table_exists = cur.fetchone()['exists']
    
    if t4_table_exists:
        cur.execute("""
            SELECT * FROM t4_slips
            WHERE employee_id IN (SELECT employee_id FROM employees 
                                  WHERE LOWER(full_name) LIKE '%paul%richard%')
            ORDER BY tax_year
        """)
        t4_records = cur.fetchall()
        
        if t4_records:
            for t4 in t4_records:
                print(f"\nYear {t4['tax_year']}: Employee ID {t4['employee_id']}")
                print(f"  Box 14 (Employment Income): ${t4.get('box_14_employment_income', 0):.2f}")
                print(f"  Box 22 (Income Tax): ${t4.get('box_22_income_tax', 0):.2f}")
                print(f"  Box 16 (CPP): ${t4.get('box_16_cpp', 0):.2f}")
                print(f"  Box 18 (EI): ${t4.get('box_18_ei', 0):.2f}")
        else:
            print("No T4 records found in t4_slips table")
    else:
        print("[FAIL] t4_slips table does not exist")
    
    # 3. Check driver_payroll table for Paul's pay records
    print("\n\n3. PAUL'S PAYROLL RECORDS (driver_payroll table):")
    print("-" * 80)
    
    # Get Paul's employee IDs
    paul_emp_ids = [rec['employee_id'] for rec in paul_records]
    paul_emp_numbers = [rec['employee_number'] for rec in paul_records]
    
    cur.execute("""
        SELECT year, month, COUNT(*) as entries,
               SUM(gross_pay) as total_gross,
               SUM(cpp) as total_cpp,
               SUM(ei) as total_ei,
               SUM(tax) as total_tax,
               SUM(net_pay) as total_net,
               SUM(t4_box_14) as t4_box_14_total,
               MAX(quickbooks_source) as qb_source
        FROM driver_payroll
        WHERE employee_id = ANY(%s)
           OR driver_id = ANY(%s)
        GROUP BY year, month
        ORDER BY year, month
    """, (paul_emp_ids, paul_emp_numbers))
    payroll_summary = cur.fetchall()
    
    if payroll_summary:
        print(f"\nFound {len(payroll_summary)} month/year combinations with payroll entries")
        
        yearly_totals = {}
        for entry in payroll_summary:
            year = entry['year']
            if year not in yearly_totals:
                yearly_totals[year] = {
                    'entries': 0, 'gross': 0, 'cpp': 0, 'ei': 0, 
                    'tax': 0, 'net': 0, 't4_box_14': 0
                }
            yearly_totals[year]['entries'] += entry['entries']
            yearly_totals[year]['gross'] += entry['total_gross'] or 0
            yearly_totals[year]['cpp'] += entry['total_cpp'] or 0
            yearly_totals[year]['ei'] += entry['total_ei'] or 0
            yearly_totals[year]['tax'] += entry['total_tax'] or 0
            yearly_totals[year]['net'] += entry['total_net'] or 0
            yearly_totals[year]['t4_box_14'] += entry['t4_box_14_total'] or 0
        
        print("\nYEARLY SUMMARY:")
        print(f"{'Year':<6} {'Entries':<8} {'Gross Pay':<12} {'CPP':<10} {'EI':<10} "
              f"{'Tax':<10} {'Net Pay':<12} {'T4 Box 14':<12}")
        print("-" * 90)
        
        for year in sorted(yearly_totals.keys()):
            totals = yearly_totals[year]
            print(f"{year:<6} {totals['entries']:<8} "
                  f"${totals['gross']:>10,.2f} ${totals['cpp']:>8,.2f} "
                  f"${totals['ei']:>8,.2f} ${totals['tax']:>8,.2f} "
                  f"${totals['net']:>10,.2f} ${totals['t4_box_14']:>10,.2f}")
        
        # Special focus on 2012
        print("\n\n🔍 2012 DETAILED ANALYSIS:")
        print("-" * 80)
        cur.execute("""
            SELECT month, COUNT(*) as entries,
                   SUM(gross_pay) as gross,
                   SUM(t4_box_14) as t4_income,
                   MAX(quickbooks_source) as source
            FROM driver_payroll
            WHERE year = 2012
              AND (employee_id = ANY(%s) OR driver_id = ANY(%s))
            GROUP BY month
            ORDER BY month
        """, (paul_emp_ids, paul_emp_numbers))
        monthly_2012 = cur.fetchall()
        
        if monthly_2012:
            for month_data in monthly_2012:
                print(f"Month {month_data['month']:02d}: {month_data['entries']} entries, "
                      f"Gross: ${month_data['gross'] or 0:.2f}, "
                      f"T4 Income: ${month_data['t4_income'] or 0:.2f}, "
                      f"Source: {month_data['source']}")
        else:
            print("[FAIL] NO 2012 PAYROLL DATA FOUND FOR PAUL")
    else:
        print("[FAIL] No payroll records found in driver_payroll table")
    
    # 4. Check staging_driver_pay for Paul
    print("\n\n4. PAUL'S STAGING PAY RECORDS:")
    print("-" * 80)
    
    cur.execute("""
        SELECT COUNT(*) as total_records,
               MIN(txn_date) as earliest_date,
               MAX(txn_date) as latest_date,
               SUM(gross_amount) as total_gross
        FROM staging_driver_pay
        WHERE driver_id = ANY(%s)
    """, (paul_emp_numbers,))
    staging_summary = cur.fetchone()
    
    if staging_summary and staging_summary['total_records'] > 0:
        print(f"\nFound {staging_summary['total_records']} staging records")
        print(f"Date range: {staging_summary['earliest_date']} to {staging_summary['latest_date']}")
        print(f"Total gross: ${staging_summary['total_gross'] or 0:.2f}")
        
        # 2012 specific
        cur.execute("""
            SELECT EXTRACT(YEAR FROM txn_date) as year,
                   COUNT(*) as records,
                   SUM(gross_amount) as total_gross
            FROM staging_driver_pay
            WHERE driver_id = ANY(%s)
              AND EXTRACT(YEAR FROM txn_date) = 2012
            GROUP BY EXTRACT(YEAR FROM txn_date)
        """, (paul_emp_numbers,))
        staging_2012 = cur.fetchone()
        
        if staging_2012:
            print(f"\n2012 Staging: {staging_2012['records']} records, "
                  f"Total: ${staging_2012['total_gross'] or 0:.2f}")
    else:
        print("No staging pay records found for Paul")
    
    # 5. Summary and recommendations
    print("\n\n" + "=" * 80)
    print("ANALYSIS SUMMARY:")
    print("=" * 80)
    
    print("\n📋 EMPLOYEE RECORD STATUS:")
    print(f"   - Found {len(paul_records)} employee records")
    print(f"   - ID 143 has complete SIN (637 660 614) and hire date (2005-01-01)")
    print(f"   - ID 275 is LEGACY stub without SIN (should be merged/deleted)")
    
    if payroll_summary:
        total_years = len(set(entry['year'] for entry in payroll_summary))
        total_gross = sum(yearly_totals[y]['gross'] for y in yearly_totals)
        print(f"\n💰 PAYROLL STATUS:")
        print(f"   - Payroll data exists for {total_years} years")
        print(f"   - Total gross pay: ${total_gross:,.2f}")
        
        if 2012 in yearly_totals:
            print(f"\n🔍 2012 SPECIFIC:")
            print(f"   - 2012 gross pay: ${yearly_totals[2012]['gross']:,.2f}")
            print(f"   - 2012 T4 Box 14: ${yearly_totals[2012]['t4_box_14']:,.2f}")
            if yearly_totals[2012]['t4_box_14'] > 0:
                print(f"   [OK] T4 income reported in driver_payroll (suggests CRA submission)")
            else:
                print(f"   [WARN]  NO T4 income in driver_payroll (may indicate held back pay)")
        else:
            print(f"\n[FAIL] 2012 CRITICAL ISSUE:")
            print(f"   - NO 2012 payroll data found in driver_payroll table")
            print(f"   - This suggests pay may have been held back or not recorded")
    
    print("\n\n🎯 NEXT STEPS:")
    print("1. Check if 2012 T4 was actually filed with CRA (external verification needed)")
    print("2. If T4 was filed: Pay was claimed, deductions applied")
    print("3. If T4 NOT filed: Pay may have been deferred/held back")
    print("4. Review staging_driver_pay for unprocessed 2012 data")
    print("5. Consolidate duplicate employee records (keep ID 143, delete 275)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    investigate_paul_records()

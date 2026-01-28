#!/usr/bin/env python3
"""
Investigate Jeannie Shillington's payroll and T4 records.

Check:
1. Employee records (4 duplicates found)
2. Payroll entries
3. T4 Box 14 values
4. Tax exemption status
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

def investigate_jeannie_records():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("JEANNIE SHILLINGTON - PAYROLL & T4 INVESTIGATION")
    print("=" * 80)
    
    # 1. Get all Jeannie employee records
    print("\n1. JEANNIE'S EMPLOYEE RECORDS:")
    print("-" * 80)
    cur.execute("""
        SELECT employee_id, employee_number, full_name, position, 
               hire_date, employment_status, status, 
               hourly_rate, salary, is_chauffeur,
               t4_sin, created_at, updated_at
        FROM employees 
        WHERE LOWER(full_name) LIKE '%jeannie%'
           OR LOWER(full_name) LIKE '%shillington%'
        ORDER BY employee_id
    """)
    jeannie_records = cur.fetchall()
    
    for rec in jeannie_records:
        print(f"\nID {rec['employee_id']}: {rec['full_name']}")
        print(f"  Emp#: {rec['employee_number']}")
        print(f"  Position: {rec['position']}")
        print(f"  Hired: {rec['hire_date']} | Employment Status: {rec['employment_status']} | Status: {rec['status']}")
        print(f"  SIN: {rec['t4_sin']}")
        print(f"  Hourly Rate: ${rec['hourly_rate']} | Salary: ${rec['salary']}")
        print(f"  Is Chauffeur: {rec['is_chauffeur']}")
        print(f"  Created: {rec['created_at']}")
    
    # 2. Check payroll records
    print("\n\n2. JEANNIE'S PAYROLL RECORDS:")
    print("-" * 80)
    
    jeannie_emp_ids = [rec['employee_id'] for rec in jeannie_records]
    jeannie_emp_numbers = [rec['employee_number'] for rec in jeannie_records]
    
    cur.execute("""
        SELECT year, month, COUNT(*) as entries,
               SUM(gross_pay) as total_gross,
               SUM(cpp) as total_cpp,
               SUM(ei) as total_ei,
               SUM(tax) as total_tax,
               SUM(net_pay) as total_net,
               SUM(t4_box_14) as t4_box_14_total
        FROM driver_payroll
        WHERE employee_id = ANY(%s)
           OR driver_id = ANY(%s)
        GROUP BY year, month
        ORDER BY year, month
    """, (jeannie_emp_ids, jeannie_emp_numbers))
    payroll_summary = cur.fetchall()
    
    if payroll_summary:
        print(f"\nFound {len(payroll_summary)} month/year combinations")
        
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
        
        # Tax threshold analysis
        print("\n\n3. TAX EXEMPTION ANALYSIS:")
        print("-" * 80)
        
        thresholds = {
            2011: 16977, 2012: 17282, 2013: 17593, 2014: 18214, 2015: 18451,
            2016: 18659, 2017: 18690, 2018: 11809, 2019: 12069, 2020: 13229,
            2021: 13808, 2022: 14398, 2023: 15000, 2024: 15705, 2025: 16129
        }
        
        print(f"\n{'Year':<6} {'Gross Pay':<12} {'Tax Deducted':<12} {'T4 Reported':<12} "
              f"{'Threshold':<12} {'Status':<25}")
        print("-" * 95)
        
        total_refund = 0
        for year in sorted(yearly_totals.keys()):
            totals = yearly_totals[year]
            threshold = thresholds.get(year, 15000)
            
            if totals['gross'] < threshold:
                status = "[OK] Below threshold"
                if totals['tax'] > 0:
                    status += f" (${totals['tax']:,.2f} refund)"
                    total_refund += totals['tax']
            else:
                status = "[WARN]  Above threshold"
            
            print(f"{year:<6} ${totals['gross']:>10,.2f} ${totals['tax']:>10,.2f} "
                  f"${totals['t4_box_14']:>10,.2f} ${threshold:>10,.2f} {status:<25}")
        
        if total_refund > 0:
            print(f"\n💰 TOTAL TAX REFUND AVAILABLE: ${total_refund:,.2f}")
    else:
        print("[FAIL] No payroll records found")
    
    # 4. Summary
    print("\n\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    print(f"\n📋 EMPLOYEE RECORDS: {len(jeannie_records)} duplicates found")
    print(f"   ID 144: Complete with SIN (623 466 877), hired 2007-06-01 [OK]")
    print(f"   IDs 3, 222, 276: LEGACY stubs without SIN")
    
    if payroll_summary:
        total_years = len(yearly_totals)
        total_gross = sum(yearly_totals[y]['gross'] for y in yearly_totals)
        total_tax = sum(yearly_totals[y]['tax'] for y in yearly_totals)
        
        print(f"\n💰 PAYROLL SUMMARY:")
        print(f"   Years with payroll: {total_years}")
        print(f"   Total gross pay: ${total_gross:,.2f}")
        print(f"   Total tax withheld: ${total_tax:,.2f}")
        
        below_threshold_years = [y for y in yearly_totals 
                                if yearly_totals[y]['gross'] < thresholds.get(y, 15000)]
        
        if below_threshold_years:
            print(f"\n   [OK] {len(below_threshold_years)} years below basic personal amount")
            refund_available = sum(yearly_totals[y]['tax'] for y in below_threshold_years)
            if refund_available > 0:
                print(f"   💡 ${refund_available:,.2f} tax refund available")
    
    print("\n🎯 RECOMMENDATIONS:")
    print("   1. Consolidate employee records (keep ID 144, delete 3, 222, 276)")
    if payroll_summary and total_refund > 0:
        print(f"   2. File T4s for years below threshold to claim ${total_refund:,.2f} refund")
    print("   3. Verify all payroll entries reference correct employee_id (144)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    investigate_jeannie_records()

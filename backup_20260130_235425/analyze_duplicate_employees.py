#!/usr/bin/env python3
"""
Analyze duplicate employee records to determine which to keep.

Strategy:
- Keep record with most complete data (SIN, hire date, etc.)
- Prioritize records with recent payroll activity
- Check for foreign key references in charters, driver_payroll
- Show which record should be kept and which should be merged/deleted
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def analyze_duplicate_employee(conn, employee_ids, employee_name):
    """Analyze which duplicate employee record to keep."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print(f"\n{'=' * 80}")
    print(f"ANALYZING: {employee_name}")
    print(f"{'=' * 80}")
    
    records = []
    
    for emp_id in employee_ids:
        # Get employee details
        cur.execute("""
            SELECT employee_id, employee_number, full_name, 
                   hire_date, t4_sin, cell_phone, email_address,
                   street_address, city, province, postal_code,
                   hourly_rate, salary, position, employment_status, status,
                   created_at, updated_at
            FROM employees
            WHERE employee_id = %s
        """, (emp_id,))
        emp_data = cur.fetchone()
        
        if not emp_data:
            continue
        
        # Count payroll records
        cur.execute("""
            SELECT COUNT(*) as count,
                   MIN(year) as first_year,
                   MAX(year) as last_year,
                   SUM(gross_pay) as total_pay
            FROM driver_payroll
            WHERE employee_id = %s OR driver_id = %s
        """, (emp_id, emp_data['employee_number']))
        payroll_data = cur.fetchone()
        
        # Count charter assignments
        cur.execute("""
            SELECT COUNT(*) as count,
                   MIN(charter_date) as first_charter,
                   MAX(charter_date) as last_charter
            FROM charters
            WHERE assigned_driver_id = %s
        """, (emp_id,))
        charter_data = cur.fetchone()
        
        # Calculate completeness score
        score = 0
        if emp_data['t4_sin']: score += 20
        if emp_data['hire_date']: score += 15
        if emp_data['cell_phone']: score += 5
        if emp_data['email_address']: score += 5
        if emp_data['street_address']: score += 10
        if emp_data['city']: score += 5
        if emp_data['postal_code']: score += 5
        if payroll_data['count'] > 0: score += 20
        if charter_data['count'] > 0: score += 10
        if emp_data['employment_status'] == 'active': score += 5
        
        records.append({
            'emp_data': emp_data,
            'payroll_data': payroll_data,
            'charter_data': charter_data,
            'score': score
        })
    
    # Sort by score (highest first)
    records.sort(key=lambda x: x['score'], reverse=True)
    
    # Display analysis
    for i, rec in enumerate(records):
        emp = rec['emp_data']
        payroll = rec['payroll_data']
        charter = rec['charter_data']
        
        keep_flag = "[OK] KEEP" if i == 0 else "[FAIL] MERGE/DELETE"
        
        print(f"\n{keep_flag} - Record #{i+1}: ID {emp['employee_id']} (Score: {rec['score']}/100)")
        print(f"{'─' * 80}")
        print(f"  Emp#: {emp['employee_number']}")
        print(f"  Name: {emp['full_name']}")
        print(f"  Status: {emp['employment_status']} / {emp['status']}")
        print(f"  Created: {emp['created_at']} | Updated: {emp['updated_at']}")
        
        print(f"\n  PERSONAL DATA:")
        print(f"    SIN: {'[OK] ' + emp['t4_sin'] if emp['t4_sin'] else '[FAIL] Missing'}")
        print(f"    Hire Date: {'[OK] ' + str(emp['hire_date']) if emp['hire_date'] else '[FAIL] Missing'}")
        print(f"    Phone: {'[OK] ' + emp['cell_phone'] if emp['cell_phone'] else '[FAIL] Missing'}")
        print(f"    Email: {'[OK] ' + emp['email_address'] if emp['email_address'] else '[FAIL] Missing'}")
        print(f"    Address: {'[OK] ' + (emp['street_address'] or '') if emp['street_address'] else '[FAIL] Missing'}")
        
        print(f"\n  PAYROLL RECORDS:")
        if payroll['count'] > 0:
            print(f"    [OK] {payroll['count']} payroll entries")
            print(f"    Years: {payroll['first_year']} to {payroll['last_year']}")
            print(f"    Total pay: ${payroll['total_pay']:,.2f}")
        else:
            print(f"    [FAIL] No payroll records")
        
        print(f"\n  CHARTER ASSIGNMENTS:")
        if charter['count'] > 0:
            print(f"    [OK] {charter['count']} charter assignments")
            print(f"    Dates: {charter['first_charter']} to {charter['last_charter']}")
        else:
            print(f"    [FAIL] No charter assignments")
        
        if i == 0:
            print(f"\n  💡 RECOMMENDATION: KEEP this record (highest completeness)")
        else:
            print(f"\n  💡 RECOMMENDATION: Merge data into ID {records[0]['emp_data']['employee_id']}, then delete")
    
    cur.close()
    return records[0]['emp_data']['employee_id'] if records else None

def main():
    parser = argparse.ArgumentParser(description='Analyze duplicate employees')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show analysis without making changes (default)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    
    print("=" * 80)
    print("DUPLICATE EMPLOYEE CONSOLIDATION ANALYSIS")
    print("=" * 80)
    print("\nThis script analyzes duplicate employee records to determine")
    print("which record has the most complete data and should be kept.")
    print("\nScoring criteria:")
    print("  - SIN present: +20 points")
    print("  - Payroll records exist: +20 points")
    print("  - Hire date present: +15 points")
    print("  - Charter assignments: +10 points")
    print("  - Address present: +10 points")
    print("  - Phone/email: +5 points each")
    print("  - Active status: +5 points")
    
    # Known duplicates
    duplicates = {
        'Logan Mosinsky': [126, 190, 289],
        'Paul D Richard': [143, 275],  # ID 49 is Paul Daniel Mansell (different person)
        'Jeannie Shillington': [3, 144, 222, 276]
    }
    
    keep_ids = {}
    
    for name, emp_ids in duplicates.items():
        keep_id = analyze_duplicate_employee(conn, emp_ids, name)
        if keep_id:
            keep_ids[name] = {
                'keep': keep_id,
                'delete': [eid for eid in emp_ids if eid != keep_id]
            }
    
    # Summary
    print(f"\n\n{'=' * 80}")
    print("CONSOLIDATION PLAN SUMMARY")
    print(f"{'=' * 80}")
    
    for name, plan in keep_ids.items():
        print(f"\n{name}:")
        print(f"  [OK] KEEP: Employee ID {plan['keep']}")
        print(f"  [FAIL] DELETE: Employee IDs {plan['delete']}")
        print(f"  📋 ACTION: Update foreign keys in charters, driver_payroll to point to {plan['keep']}")
    
    print(f"\n\n💡 NEXT STEPS:")
    print(f"   1. Review the analysis above")
    print(f"   2. Verify the 'KEEP' record for each employee is correct")
    print(f"   3. Run consolidation script with --write flag to apply changes")
    print(f"   4. Changes will:")
    print(f"      a) Update charters.assigned_driver_id to point to kept record")
    print(f"      b) Update driver_payroll.employee_id to point to kept record")
    print(f"      c) Delete duplicate employee records")
    
    conn.close()

if __name__ == '__main__':
    main()

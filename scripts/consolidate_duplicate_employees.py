#!/usr/bin/env python3
"""
Consolidate duplicate employees by MERGING data into the record with payroll history.

Strategy:
- KEEP the employee ID that has payroll/charter records (the historical data)
- COPY SIN, hire date, address, etc. from the other record to it
- DELETE the duplicate records
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

def consolidate_employees(conn, keep_id, delete_ids, dry_run=True):
    """Merge data from delete_ids into keep_id, then delete duplicates."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get the keep record
    cur.execute("SELECT * FROM employees WHERE employee_id = %s", (keep_id,))
    keep_record = cur.fetchone()
    
    if not keep_record:
        print(f"[FAIL] ERROR: Employee ID {keep_id} not found!")
        return False
    
    print(f"\n{'─' * 80}")
    print(f"CONSOLIDATING INTO: ID {keep_id} - {keep_record['full_name']}")
    print(f"{'─' * 80}")
    
    # Collect data from records to be deleted
    merge_data = {}
    
    for del_id in delete_ids:
        cur.execute("SELECT * FROM employees WHERE employee_id = %s", (del_id,))
        del_record = cur.fetchone()
        
        if not del_record:
            print(f"[WARN]  Warning: Employee ID {del_id} not found, skipping")
            continue
        
        print(f"\nMERGING FROM: ID {del_id} - {del_record['full_name']}")
        
        # Copy non-null values from delete record if keep record is missing them
        fields_to_check = [
            't4_sin', 'hire_date', 'cell_phone', 'email_address',
            'street_address', 'city', 'province', 'postal_code', 'country',
            'driver_license_number', 'license_expiry', 'medical_cert_expiry'
        ]
        
        for field in fields_to_check:
            keep_val = keep_record.get(field)
            del_val = del_record.get(field)
            
            # If keep record is missing this field but delete record has it, copy it
            if (not keep_val or keep_val == '') and (del_val and del_val != ''):
                if field not in merge_data:
                    merge_data[field] = del_val
                    print(f"  📋 Will copy {field}: {del_val}")
    
    # Build UPDATE query
    if merge_data:
        set_clauses = []
        values = []
        for field, value in merge_data.items():
            set_clauses.append(f"{field} = %s")
            values.append(value)
        
        values.append(keep_id)
        update_sql = f"""
            UPDATE employees 
            SET {', '.join(set_clauses)}
            WHERE employee_id = %s
        """
        
        if dry_run:
            print(f"\n🔍 DRY RUN - Would execute:")
            print(f"   {update_sql}")
            print(f"   Values: {values}")
        else:
            print(f"\n✍️  Updating employee ID {keep_id}...")
            cur.execute(update_sql, values)
            print(f"   [OK] Updated {cur.rowcount} record")
    else:
        print(f"\n[OK] No missing data to merge - keep record is already complete")
    
    # Check for any foreign key references in delete records
    for del_id in delete_ids:
        print(f"\n🔍 Checking foreign key references for ID {del_id}:")
        
        # Check charters
        cur.execute("""
            SELECT COUNT(*) as count FROM charters 
            WHERE assigned_driver_id = %s
        """, (del_id,))
        charter_count = cur.fetchone()['count']
        
        if charter_count > 0:
            print(f"   [WARN]  {charter_count} charters reference this employee")
            if not dry_run:
                print(f"   ✍️  Updating charters.assigned_driver_id {del_id} → {keep_id}")
                cur.execute("""
                    UPDATE charters 
                    SET assigned_driver_id = %s 
                    WHERE assigned_driver_id = %s
                """, (keep_id, del_id))
                print(f"   [OK] Updated {cur.rowcount} charters")
        else:
            print(f"   [OK] No charter references")
        
        # Check driver_payroll by employee_id
        cur.execute("""
            SELECT COUNT(*) as count FROM driver_payroll 
            WHERE employee_id = %s
        """, (del_id,))
        payroll_count = cur.fetchone()['count']
        
        if payroll_count > 0:
            print(f"   [WARN]  {payroll_count} payroll records reference employee_id")
            if not dry_run:
                print(f"   ✍️  Updating driver_payroll.employee_id {del_id} → {keep_id}")
                cur.execute("""
                    UPDATE driver_payroll 
                    SET employee_id = %s 
                    WHERE employee_id = %s
                """, (keep_id, del_id))
                print(f"   [OK] Updated {cur.rowcount} payroll records")
        else:
            print(f"   [OK] No payroll employee_id references")
    
    # Delete duplicate records
    if not dry_run:
        print(f"\n🗑️  Deleting duplicate employee records...")
        for del_id in delete_ids:
            cur.execute("DELETE FROM employees WHERE employee_id = %s", (del_id,))
            print(f"   [OK] Deleted employee ID {del_id}")
        
        conn.commit()
        print(f"\n[OK] CONSOLIDATION COMPLETE")
    else:
        print(f"\n🔍 DRY RUN - No changes made")
        print(f"   Run with --write to apply changes")
    
    cur.close()
    return True

def main():
    parser = argparse.ArgumentParser(description='Consolidate duplicate employees')
    parser.add_argument('--write', action='store_true', 
                       help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    
    print("=" * 80)
    print("EMPLOYEE CONSOLIDATION - MERGE DATA INTO RECORDS WITH HISTORY")
    print("=" * 80)
    
    if args.write:
        print("\n[WARN]  WRITE MODE - Changes will be applied!")
    else:
        print("\n🔍 DRY RUN MODE - No changes will be made")
        print("   Run with --write to apply changes")
    
    # Consolidation plan based on analysis:
    # - Keep records with payroll/charter history
    # - Merge SIN/personal data from other records
    # - Delete empty duplicate records
    
    consolidations = [
        {
            'name': 'Jeannie Shillington',
            'keep': 3,      # Has 1,421 payroll entries and charters
            'delete': [144, 222, 276]  # 144 has SIN/hire date, others are empty
        },
        {
            'name': 'Logan Mosinsky',
            'keep': 126,    # Has 4 payroll entries and charters
            'delete': [190, 289]  # 190 has same SIN (duplicate), 289 is empty
        },
        {
            'name': 'Paul D Richard',
            'keep': 143,    # Has SIN/hire date (no payroll but most complete)
            'delete': [275]  # Empty LEGACY record
        }
    ]
    
    for plan in consolidations:
        print(f"\n{'═' * 80}")
        print(f"{plan['name'].upper()}")
        print(f"{'═' * 80}")
        print(f"KEEP: Employee ID {plan['keep']}")
        print(f"DELETE: Employee IDs {plan['delete']}")
        
        success = consolidate_employees(conn, plan['keep'], plan['delete'], 
                                       dry_run=not args.write)
        
        if not success:
            print(f"[FAIL] Failed to consolidate {plan['name']}")
            break
    
    if args.write:
        print(f"\n\n{'═' * 80}")
        print("ALL CONSOLIDATIONS COMPLETE")
        print(f"{'═' * 80}")
    else:
        print(f"\n\n{'═' * 80}")
        print("DRY RUN COMPLETE - Review output above")
        print("Run with --write to apply changes")
        print(f"{'═' * 80}")
    
    conn.close()

if __name__ == '__main__':
    main()

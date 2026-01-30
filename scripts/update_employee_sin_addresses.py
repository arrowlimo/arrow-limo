#!/usr/bin/env python3
"""
Update employees table with SIN numbers and addresses from pay statement data.

This script updates existing employee records with:
- t4_sin (Social Insurance Numbers)
- hire_date
- address information (from street1, city, postal_code in staging)
- phone numbers

Data source: staging_employee_reference_data (extracted from pay statements)

Usage:
    python scripts/update_employee_sin_addresses.py --dry-run
    python scripts/update_employee_sin_addresses.py --write
"""

import os
import sys
import psycopg2
from datetime import datetime
import argparse

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_updates(cur):
    """Analyze what updates would be made."""
    print("\n" + "="*80)
    print("ANALYZING EMPLOYEE DATA UPDATES")
    print("="*80)
    
    # Find employees that would be updated
    cur.execute("""
        SELECT 
            e.employee_id,
            e.full_name as current_name,
            e.t4_sin as current_sin,
            e.hire_date as current_hire_date,
            serd.employee_name as staging_name,
            serd.sin as staging_sin,
            serd.hire_date as staging_hire_date,
            serd.street1,
            serd.city,
            serd.postal_code,
            serd.main_phone
        FROM employees e
        INNER JOIN staging_employee_reference_data serd 
            ON LOWER(TRIM(e.full_name)) = LOWER(TRIM(serd.employee_name))
        WHERE (e.t4_sin IS NULL OR e.t4_sin = '')
        AND serd.sin IS NOT NULL 
        AND serd.sin != ''
        ORDER BY e.full_name
    """)
    
    updates = cur.fetchall()
    
    if not updates:
        print("\n[WARN]  No employees found that need SIN updates")
        return []
    
    print(f"\n📊 Found {len(updates)} employees that will be updated:")
    print(f"\n{'Employee Name':<30} {'Current SIN':<15} {'New SIN':<15} {'Hire Date':<12}")
    print("-"*80)
    
    for row in updates:
        emp_id, curr_name, curr_sin, curr_hire, stage_name, stage_sin, stage_hire, street, city, postal, phone = row
        curr_sin_display = curr_sin if curr_sin else "NULL"
        hire_display = stage_hire if stage_hire else "N/A"
        print(f"{curr_name:<30} {curr_sin_display:<15} {stage_sin:<15} {hire_display}")
    
    # Show detailed info for key employees
    print("\n" + "="*80)
    print("DETAILED UPDATE INFORMATION")
    print("="*80)
    
    for row in updates:
        emp_id, curr_name, curr_sin, curr_hire, stage_name, stage_sin, stage_hire, street, city, postal, phone = row
        
        print(f"\n{curr_name} (ID: {emp_id})")
        print(f"  Current SIN: {curr_sin if curr_sin else 'NULL'}")
        print(f"  New SIN: {stage_sin}")
        print(f"  Current Hire Date: {curr_hire if curr_hire else 'NULL'}")
        print(f"  New Hire Date: {stage_hire if stage_hire else 'N/A'}")
        
        if street or city:
            address = f"{street or ''}, {city or ''} {postal or ''}".strip(', ')
            print(f"  Address: {address}")
        
        if phone:
            print(f"  Phone: {phone}")
    
    return updates

def check_duplicate_employees(cur):
    """Check for duplicate employee records that should be consolidated."""
    print("\n" + "="*80)
    print("DUPLICATE EMPLOYEE ANALYSIS")
    print("="*80)
    
    # Find employees with same name
    cur.execute("""
        WITH name_groups AS (
            SELECT 
                LOWER(TRIM(full_name)) as normalized_name,
                COUNT(*) as count,
                STRING_AGG(employee_id::TEXT || ': ' || full_name, ', ' ORDER BY employee_id) as ids_and_names
            FROM employees
            GROUP BY LOWER(TRIM(full_name))
            HAVING COUNT(*) > 1
        )
        SELECT normalized_name, count, ids_and_names
        FROM name_groups
        ORDER BY count DESC, normalized_name
    """)
    
    duplicates = cur.fetchall()
    
    if not duplicates:
        print("\n[OK] No duplicate employee names found")
        return
    
    print(f"\n[WARN]  Found {len(duplicates)} employee names with multiple records:")
    print(f"\n{'Name':<30} {'Count':<10} {'Employee IDs'}")
    print("-"*80)
    
    for name, count, ids_names in duplicates:
        print(f"{name:<30} {count:<10} {ids_names}")
    
    print("\n🔧 NOTE: These duplicates should be consolidated manually after SIN update")
    print("   Example: Paul D Richard has 3 records - merge into single record with correct SIN")

def apply_updates(cur, conn, dry_run=True):
    """Apply SIN and address updates to employees table."""
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN MODE - No changes will be made")
        print("="*80)
        return
    
    print("\n" + "="*80)
    print("APPLYING UPDATES")
    print("="*80)
    
    # Update employees with SIN, hire date, and contact info
    update_query = """
        UPDATE employees e
        SET 
            t4_sin = serd.sin,
            hire_date = serd.hire_date,
            phone = COALESCE(e.phone, serd.main_phone),
            updated_at = CURRENT_TIMESTAMP
        FROM staging_employee_reference_data serd
        WHERE LOWER(TRIM(e.full_name)) = LOWER(TRIM(serd.employee_name))
        AND (e.t4_sin IS NULL OR e.t4_sin = '')
        AND serd.sin IS NOT NULL 
        AND serd.sin != ''
    """
    
    try:
        cur.execute(update_query)
        updated_count = cur.rowcount
        print(f"\n[OK] Updated {updated_count} employee records with SIN/hire date/phone")
        
        # Show what was updated
        cur.execute("""
            SELECT 
                e.employee_id,
                e.full_name,
                e.t4_sin,
                e.hire_date,
                e.phone
            FROM employees e
            INNER JOIN staging_employee_reference_data serd 
                ON LOWER(TRIM(e.full_name)) = LOWER(TRIM(serd.employee_name))
            WHERE e.t4_sin IS NOT NULL
            ORDER BY e.full_name
        """)
        
        print(f"\n{'Employee':<30} {'SIN':<15} {'Hire Date':<12} {'Phone':<15}")
        print("-"*80)
        for row in cur.fetchall():
            emp_id, name, sin, hire, phone = row
            hire_display = hire.strftime('%Y-%m-%d') if hire else 'N/A'
            phone_display = phone if phone else 'N/A'
            print(f"{name:<30} {sin:<15} {hire_display:<12} {phone_display:<15}")
        
        conn.commit()
        print("\n[OK] Changes committed to database")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error applying updates: {e}")
        raise

def create_address_mapping(cur, conn, dry_run=True):
    """
    Create or update address records for employees if needed.
    Note: employees table may not have address fields, check schema first.
    """
    
    # Check if employees table has address field
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'employees' 
        AND column_name IN ('address', 'street1', 'city', 'postal_code')
    """)
    
    address_columns = [row[0] for row in cur.fetchall()]
    
    if not address_columns:
        print("\n📋 NOTE: employees table has no address fields")
        print("   Address data from staging: street1, city, postal_code")
        print("   Consider adding address fields or creating employee_addresses table")
        return
    
    print(f"\n📋 employees table has address columns: {', '.join(address_columns)}")
    
    # If we have address column, suggest manual review
    print("\n[WARN]  Address update logic depends on table schema")
    print("   Review staging_employee_reference_data for address data:")
    cur.execute("""
        SELECT employee_name, street1, city, postal_code
        FROM staging_employee_reference_data
        WHERE street1 IS NOT NULL
        ORDER BY employee_name
    """)
    
    print(f"\n{'Employee':<30} {'Address':<60}")
    print("-"*90)
    for row in cur.fetchall():
        name, street, city, postal = row
        address = f"{street}, {city} {postal or ''}".strip()
        print(f"{name:<30} {address:<60}")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Update employees table with SIN and address data from pay statements'
    )
    parser.add_argument('--write', action='store_true',
                       help='Apply updates to database (default is dry-run)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze only, do not apply updates (default)')
    
    args = parser.parse_args()
    
    # Default to dry-run unless --write is specified
    dry_run = not args.write
    
    print("="*80)
    print("EMPLOYEE SIN/ADDRESS UPDATE FROM PAY STATEMENTS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'WRITE (applying changes)'}")
    print("="*80)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Analyze what updates would be made
        updates = analyze_updates(cur)
        
        if not updates:
            print("\n[OK] No updates needed - all employees already have SIN data")
            cur.close()
            conn.close()
            return
        
        # Check for duplicates
        check_duplicate_employees(cur)
        
        # Show address data available
        create_address_mapping(cur, conn, dry_run)
        
        # Apply updates if not dry-run
        if not dry_run:
            print("\n" + "="*80)
            response = input("Proceed with updates? (yes/no): ")
            if response.lower() != 'yes':
                print("[FAIL] Updates cancelled")
                cur.close()
                conn.close()
                return
            
            apply_updates(cur, conn, dry_run=False)
        else:
            print("\n" + "="*80)
            print("💡 To apply these updates, run:")
            print("   python scripts/update_employee_sin_addresses.py --write")
        
        cur.close()
        conn.close()
        
        print("\n[OK] Script completed successfully")
        
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

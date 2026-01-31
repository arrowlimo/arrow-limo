#!/usr/bin/env python3
"""
Add address columns to employees table and populate from staging data.

Adds: street_address, city, province, postal_code, country
Then updates with data from staging_employee_reference_data

Usage:
    python scripts/add_employee_address_columns.py --dry-run
    python scripts/add_employee_address_columns.py --write
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

def check_columns_exist(cur):
    """Check if address columns already exist."""
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'employees' 
        AND column_name IN ('street_address', 'city', 'province', 'postal_code', 'country')
    """)
    existing = [row[0] for row in cur.fetchall()]
    return existing

def add_address_columns(cur, conn, dry_run=True):
    """Add address columns to employees table."""
    
    existing = check_columns_exist(cur)
    
    if existing:
        print(f"\n[WARN]  Some address columns already exist: {', '.join(existing)}")
        missing = set(['street_address', 'city', 'province', 'postal_code', 'country']) - set(existing)
        if not missing:
            print("[OK] All address columns already exist, no need to add")
            return True
        print(f"   Will add missing columns: {', '.join(missing)}")
    
    if dry_run:
        print("\n📋 DRY RUN - Would add these columns to employees table:")
        print("   - street_address VARCHAR(200)")
        print("   - city VARCHAR(100)")
        print("   - province VARCHAR(50) DEFAULT 'AB'")
        print("   - postal_code VARCHAR(10)")
        print("   - country VARCHAR(50) DEFAULT 'Canada'")
        return False
    
    print("\n🔧 Adding address columns to employees table...")
    
    try:
        # Add columns if they don't exist
        alter_statements = [
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS street_address VARCHAR(200)",
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS province VARCHAR(50) DEFAULT 'AB'",
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS postal_code VARCHAR(10)",
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS country VARCHAR(50) DEFAULT 'Canada'"
        ]
        
        for stmt in alter_statements:
            cur.execute(stmt)
        
        conn.commit()
        print("[OK] Address columns added successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Error adding columns: {e}")
        raise

def analyze_address_updates(cur):
    """Analyze what address updates would be made."""
    print("\n" + "="*80)
    print("ADDRESS DATA AVAILABLE FROM STAGING")
    print("="*80)
    
    cur.execute("""
        SELECT 
            e.employee_id,
            e.full_name,
            serd.street1,
            serd.city,
            serd.postal_code
        FROM employees e
        INNER JOIN staging_employee_reference_data serd 
            ON LOWER(TRIM(e.full_name)) = LOWER(TRIM(serd.employee_name))
        WHERE serd.street1 IS NOT NULL
        ORDER BY e.full_name
    """)
    
    updates = cur.fetchall()
    
    if not updates:
        print("\n[WARN]  No address data found in staging")
        return []
    
    print(f"\n📊 Found address data for {len(updates)} employees:")
    print(f"\n{'Employee Name':<30} {'Street Address':<40} {'City':<20}")
    print("-"*95)
    
    for row in updates:
        emp_id, name, street, city, postal = row
        street_display = (street[:37] + '...') if street and len(street) > 40 else (street or '')
        city_display = city or ''
        print(f"{name:<30} {street_display:<40} {city_display:<20}")
    
    return updates

def apply_address_updates(cur, conn, dry_run=True):
    """Apply address updates from staging to employees table."""
    
    if dry_run:
        print("\n📋 DRY RUN - No address updates will be applied")
        return
    
    print("\n🔧 Applying address updates...")
    
    update_query = """
        UPDATE employees e
        SET 
            street_address = serd.street1,
            city = serd.city,
            postal_code = serd.postal_code,
            province = 'AB',
            country = 'Canada',
            updated_at = CURRENT_TIMESTAMP
        FROM staging_employee_reference_data serd
        WHERE LOWER(TRIM(e.full_name)) = LOWER(TRIM(serd.employee_name))
        AND serd.street1 IS NOT NULL
    """
    
    try:
        cur.execute(update_query)
        updated_count = cur.rowcount
        
        print(f"[OK] Updated {updated_count} employee records with address data")
        
        # Show what was updated
        cur.execute("""
            SELECT 
                e.employee_id,
                e.full_name,
                e.street_address,
                e.city,
                e.postal_code
            FROM employees e
            WHERE e.street_address IS NOT NULL
            ORDER BY e.full_name
        """)
        
        print(f"\n{'Employee':<30} {'Street':<40} {'City, Postal':<25}")
        print("-"*95)
        for row in cur.fetchall():
            emp_id, name, street, city, postal = row
            street_display = (street[:37] + '...') if street and len(street) > 40 else street
            location = f"{city}, {postal}" if postal else city
            print(f"{name:<30} {street_display:<40} {location:<25}")
        
        conn.commit()
        print("\n[OK] Changes committed to database")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error applying updates: {e}")
        raise

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Add address columns to employees table and populate from staging'
    )
    parser.add_argument('--write', action='store_true',
                       help='Apply changes to database (default is dry-run)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze only, do not apply changes (default)')
    
    args = parser.parse_args()
    
    # Default to dry-run unless --write is specified
    dry_run = not args.write
    
    print("="*80)
    print("ADD ADDRESS COLUMNS TO EMPLOYEES TABLE")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'WRITE (applying changes)'}")
    print("="*80)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check existing columns
        existing = check_columns_exist(cur)
        if existing:
            print(f"\n📋 Existing address columns: {', '.join(existing)}")
        else:
            print("\n📋 No address columns currently exist in employees table")
        
        # Analyze available address data
        updates = analyze_address_updates(cur)
        
        if not updates:
            print("\n[OK] No address data available in staging - nothing to do")
            cur.close()
            conn.close()
            return
        
        # Add columns (if not dry-run)
        columns_added = add_address_columns(cur, conn, dry_run)
        
        # Apply updates (if not dry-run and columns exist/added)
        if not dry_run:
            if not columns_added and not existing:
                print("\n[FAIL] Cannot apply updates - columns were not added")
                cur.close()
                conn.close()
                return
            
            print("\n" + "="*80)
            response = input("Proceed with address updates? (yes/no): ")
            if response.lower() != 'yes':
                print("[FAIL] Updates cancelled")
                cur.close()
                conn.close()
                return
            
            apply_address_updates(cur, conn, dry_run=False)
        else:
            print("\n" + "="*80)
            print("💡 To apply these changes, run:")
            print("   python scripts/add_employee_address_columns.py --write")
        
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

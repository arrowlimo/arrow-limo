"""
IMMEDIATE FIX: Populate base_wages field from gross_pay
This is the first step while we investigate the full data import issues.
"""
import psycopg2
import sys
from datetime import datetime

def create_backup(cur, conn):
    """Create backup of 2012 driver_payroll records before modification"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'driver_payroll_2012_backup_{timestamp}'
    
    print(f"Creating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM driver_payroll
        WHERE year = 2012
    """)
    conn.commit()
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"[OK] Backed up {count} records to {backup_table}")
    
    return backup_table

def main(write=False, skip_backup=False):
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("POPULATE base_wages FROM gross_pay (2012)")
    print("=" * 80)
    print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    print()
    
    # Check current state
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN base_wages IS NULL OR base_wages = 0 THEN 1 END) as empty_base,
            SUM(gross_pay) as total_gross
        FROM driver_payroll
        WHERE year = 2012
    """)
    total, empty_base, total_gross = cur.fetchone()
    
    print(f"Current state:")
    print(f"  Total 2012 records: {total}")
    print(f"  Records with empty base_wages: {empty_base}")
    print(f"  Total gross_pay: ${total_gross:,.2f}" if total_gross else "  Total gross_pay: $0.00")
    
    # Show what will be updated
    cur.execute("""
        SELECT COUNT(*), SUM(gross_pay)
        FROM driver_payroll
        WHERE year = 2012
        AND (base_wages IS NULL OR base_wages = 0)
        AND gross_pay IS NOT NULL AND gross_pay > 0
    """)
    update_count, update_sum = cur.fetchone()
    
    print(f"\nProposed update:")
    print(f"  Records to update: {update_count}")
    print(f"  Value to populate: ${update_sum:,.2f}" if update_sum else "  Value: $0.00")
    
    if not write:
        print("\n" + "=" * 80)
        print("DRY-RUN COMPLETE - No changes made")
        print("Run with --write to apply changes")
        print("=" * 80)
        cur.close()
        conn.close()
        return
    
    # Create backup
    if not skip_backup:
        backup_table = create_backup(cur, conn)
        print()
    
    # Apply update
    print("Applying update...")
    cur.execute("""
        UPDATE driver_payroll
        SET base_wages = gross_pay
        WHERE year = 2012
        AND (base_wages IS NULL OR base_wages = 0)
        AND gross_pay IS NOT NULL AND gross_pay > 0
    """)
    
    updated = cur.rowcount
    conn.commit()
    
    print(f"[OK] Updated {updated} records")
    
    # Verify
    cur.execute("""
        SELECT 
            COUNT(CASE WHEN base_wages IS NULL OR base_wages = 0 THEN 1 END) as still_empty,
            SUM(base_wages) as total_base_wages
        FROM driver_payroll
        WHERE year = 2012
    """)
    still_empty, total_base = cur.fetchone()
    
    print(f"\nPost-update state:")
    print(f"  Records still with empty base_wages: {still_empty}")
    print(f"  Total base_wages: ${total_base:,.2f}" if total_base else "  Total base_wages: $0.00")
    
    print("\n" + "=" * 80)
    print("UPDATE COMPLETE")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print("1. Review source files to identify missing payroll data")
    print("2. Determine correct interpretation of 'expenses' field")
    print("3. Re-import complete 2012 payroll from Excel/PDF source files")
    print("4. Populate gratuity_amount and hours_worked fields")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Populate base_wages from gross_pay for 2012')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--skip-backup', action='store_true', help='Skip backup creation')
    args = parser.parse_args()
    
    main(write=args.write, skip_backup=args.skip_backup)

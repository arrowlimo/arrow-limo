#!/usr/bin/env python
"""
Segregate ADJ payroll entries into payroll_adjustments table.

This script:
1. Creates payroll_adjustments table (if not exists)
2. Copies 4 ADJ driver_payroll records to payroll_adjustments
3. Marks original driver_payroll rows with payroll_class='ADJUSTMENT'
4. Provides dry-run mode for safety

Usage:
    python scripts/segregate_adj_payroll.py              # Dry-run (default)
    python scripts/segregate_adj_payroll.py --apply      # Actually execute
"""

import os
import sys
import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def run_migration(conn, dry_run=True):
    """Execute migration DDL to create tables/columns."""
    cur = conn.cursor()
    
    print("=" * 80)
    print("STEP 1: Running migration DDL")
    print("=" * 80)
    
    # Read migration file
    migration_path = 'migrations/2025-11-07_create_payroll_adjustments.sql'
    if not os.path.exists(migration_path):
        print(f"ERROR: Migration file not found: {migration_path}")
        return False
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    if dry_run:
        print("\n[DRY-RUN] Would execute migration DDL:")
        print(migration_sql[:500] + "...\n")
    else:
        print("Executing migration DDL...")
        cur.execute(migration_sql)
        conn.commit()
        print("✓ Migration DDL executed successfully\n")
    
    cur.close()
    return True

def analyze_adj_entries(conn):
    """Fetch and analyze ADJ entries before segregation."""
    cur = conn.cursor()
    
    print("=" * 80)
    print("STEP 2: Analyzing ADJ entries")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            id, driver_id, employee_id, charter_id, reserve_number,
            year, month, pay_date, gross_pay, net_pay, 
            record_notes, source, quickbooks_source
        FROM driver_payroll
        WHERE driver_id = 'ADJ'
        ORDER BY pay_date
    """)
    
    rows = cur.fetchall()
    
    print(f"\nFound {len(rows)} ADJ entries:")
    print("-" * 80)
    
    total_gross = 0
    entries = []
    
    for r in rows:
        entry = {
            'id': r[0],
            'driver_id': r[1],
            'employee_id': r[2],
            'charter_id': r[3],
            'reserve_number': r[4],
            'year': r[5],
            'month': r[6],
            'pay_date': r[7],
            'gross_pay': float(r[8] or 0),
            'net_pay': float(r[9] or 0),
            'record_notes': r[10],
            'source': r[11],
            'quickbooks_source': r[12]
        }
        entries.append(entry)
        total_gross += entry['gross_pay']
        
        print(f"ID {entry['id']}: {entry['pay_date']} | Gross ${entry['gross_pay']:,.2f} | Net ${entry['net_pay']:,.2f}")
        print(f"  Notes: {entry['record_notes']}")
        print(f"  Source: {entry['source']}")
        if entry['quickbooks_source']:
            print(f"  QB Source: {entry['quickbooks_source']}")
        print()
    
    print(f"Total gross pay: ${total_gross:,.2f}")
    print()
    
    cur.close()
    return entries

def segregate_entries(conn, entries, dry_run=True):
    """Copy ADJ entries to payroll_adjustments and mark originals."""
    cur = conn.cursor()
    
    print("=" * 80)
    print("STEP 3: Segregating ADJ entries")
    print("=" * 80)
    
    for entry in entries:
        adjustment_type = 'PDF_DB_RECONCILIATION'
        rationale = entry['record_notes'] or 'Payroll reconciliation adjustment'
        source_ref = entry['source'] or entry['quickbooks_source'] or 'Unknown'
        
        if dry_run:
            print(f"\n[DRY-RUN] Would insert into payroll_adjustments:")
            print(f"  driver_payroll_id: {entry['id']}")
            print(f"  adjustment_type: {adjustment_type}")
            print(f"  gross_amount: ${entry['gross_pay']:,.2f}")
            print(f"  net_amount: ${entry['net_pay']:,.2f}")
            print(f"  rationale: {rationale}")
            print(f"  source_reference: {source_ref}")
            print(f"  original_pay_date: {entry['pay_date']}")
            print(f"  year: {entry['year']}, month: {entry['month']}")
            print(f"  has_charter_link: {entry['charter_id'] is not None}")
            print(f"  has_employee_link: {entry['employee_id'] is not None}")
            
            print(f"\n[DRY-RUN] Would update driver_payroll id={entry['id']}:")
            print(f"  SET payroll_class = 'ADJUSTMENT'")
        else:
            # Insert into payroll_adjustments
            cur.execute("""
                INSERT INTO payroll_adjustments (
                    driver_payroll_id, adjustment_type, gross_amount, net_amount,
                    rationale, source_reference, original_pay_date, year, month,
                    has_charter_link, has_employee_link, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                entry['id'], adjustment_type, entry['gross_pay'], entry['net_pay'],
                rationale, source_ref, entry['pay_date'], entry['year'], entry['month'],
                entry['charter_id'] is not None, entry['employee_id'] is not None,
                'segregate_adj_payroll.py'
            ))
            
            # Update driver_payroll to mark as adjustment
            cur.execute("""
                UPDATE driver_payroll
                SET payroll_class = 'ADJUSTMENT'
                WHERE id = %s
            """, (entry['id'],))
            
            print(f"✓ Segregated entry id={entry['id']}")
    
    if not dry_run:
        conn.commit()
        print("\n✓ All entries segregated successfully")
    
    cur.close()

def verify_segregation(conn):
    """Verify segregation was successful."""
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("STEP 4: Verification")
    print("=" * 80)
    
    # Check payroll_adjustments count
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM payroll_adjustments")
    adj_count, adj_total = cur.fetchone()
    print(f"\npayroll_adjustments table:")
    print(f"  Records: {adj_count}")
    print(f"  Total gross: ${adj_total:,.2f}" if adj_total else "  Total gross: $0.00")
    
    # Check driver_payroll marked as ADJUSTMENT
    cur.execute("""
        SELECT COUNT(*), SUM(gross_pay) 
        FROM driver_payroll 
        WHERE payroll_class = 'ADJUSTMENT'
    """)
    marked_count, marked_total = cur.fetchone()
    print(f"\ndriver_payroll (payroll_class='ADJUSTMENT'):")
    print(f"  Records: {marked_count}")
    print(f"  Total gross: ${marked_total:,.2f}" if marked_total else "  Total gross: $0.00")
    
    # Check remaining WAGE records
    cur.execute("""
        SELECT COUNT(*), SUM(gross_pay) 
        FROM driver_payroll 
        WHERE payroll_class = 'WAGE' OR payroll_class IS NULL
    """)
    wage_count, wage_total = cur.fetchone()
    print(f"\ndriver_payroll (payroll_class='WAGE' or NULL):")
    print(f"  Records: {wage_count}")
    print(f"  Total gross: ${wage_total:,.2f}" if wage_total else "  Total gross: $0.00")
    
    print("\n✓ Verification complete")
    print("\nTo exclude adjustments from wage KPIs, use:")
    print("  WHERE payroll_class = 'WAGE' OR payroll_class IS NULL")
    
    cur.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Segregate ADJ payroll entries')
    parser.add_argument('--apply', action='store_true', help='Actually execute (default is dry-run)')
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    print("\n" + "=" * 80)
    print("ADJ PAYROLL SEGREGATION SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY-RUN (preview only)' if dry_run else 'APPLY (will modify database)'}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        conn = get_db_connection()
        
        # Step 1: Run migration
        if not run_migration(conn, dry_run):
            return 1
        
        # Step 2: Analyze ADJ entries
        entries = analyze_adj_entries(conn)
        
        if not entries:
            print("No ADJ entries found. Nothing to segregate.")
            return 0
        
        # Confirm expected count
        if len(entries) != 4:
            print(f"\n[WARN]  WARNING: Expected 4 ADJ entries, found {len(entries)}")
            if not dry_run:
                response = input("Continue anyway? (yes/no): ")
                if response.lower() != 'yes':
                    print("Aborted.")
                    return 1
        
        # Step 3: Segregate
        segregate_entries(conn, entries, dry_run)
        
        # Step 4: Verify (only if not dry-run)
        if not dry_run:
            verify_segregation(conn)
        
        conn.close()
        
        if dry_run:
            print("\n" + "=" * 80)
            print("DRY-RUN COMPLETE - No changes made to database")
            print("To actually execute, run with: --apply")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("✓ SEGREGATION COMPLETE")
            print("=" * 80)
        
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

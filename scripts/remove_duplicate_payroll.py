#!/usr/bin/env python3
"""Remove duplicate payroll entries identified in the analysis.
Creates backup before deletion and provides dry-run mode.
"""
import os, psycopg2, argparse
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

def create_backup(cur, conn):
    """Create backup of driver_payroll table"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'driver_payroll_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_name}")
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM driver_payroll")
    conn.commit()
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
    count = cur.fetchone()[0]
    print(f"✓ Backup created with {count:,} rows")
    
    return backup_name

def find_duplicate_groups(cur, year):
    """Find all duplicate groups with IDs to delete (keep lowest ID)"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    base = f"""
    WITH duplicates AS (
        SELECT 
            driver_id,
            {date_col} as pay_date,
            gross_pay,
            cpp,
            ei,
            tax,
            ARRAY_AGG(id ORDER BY id) as all_ids,
            COUNT(*) as dup_count
        FROM driver_payroll
        WHERE {date_col} >= %s AND {date_col} < %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    base += f"""
        GROUP BY driver_id, {date_col}, gross_pay, cpp, ei, tax
        HAVING COUNT(*) > 1
    )
    SELECT 
        driver_id,
        pay_date,
        gross_pay,
        cpp,
        ei,
        tax,
        all_ids,
        dup_count,
        all_ids[2:array_length(all_ids,1)] as ids_to_delete
    FROM duplicates
    ORDER BY gross_pay DESC
    """
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (start, end))
    
    groups = []
    for row in cur.fetchall():
        groups.append({
            'driver_id': row[0],
            'pay_date': row[1],
            'gross_pay': float(row[2] or 0),
            'cpp': float(row[3] or 0),
            'ei': float(row[4] or 0),
            'tax': float(row[5] or 0),
            'all_ids': row[6],
            'dup_count': int(row[7]),
            'ids_to_delete': row[8]
        })
    
    return groups

def delete_duplicates(cur, conn, groups, dry_run=True):
    """Delete duplicate IDs, keeping the lowest ID in each group"""
    all_ids_to_delete = []
    total_gross_removed = 0
    
    for group in groups:
        all_ids_to_delete.extend(group['ids_to_delete'])
        # Calculate extra amount (not the kept entry)
        extra_amount = group['gross_pay'] * (group['dup_count'] - 1)
        total_gross_removed += extra_amount
    
    print(f"\n{'='*100}")
    print(f"DUPLICATE REMOVAL {'(DRY RUN)' if dry_run else '(APPLYING)'}")
    print(f"{'='*100}")
    print(f"Duplicate Groups: {len(groups)}")
    print(f"IDs to Delete: {len(all_ids_to_delete)}")
    print(f"Gross Amount Removed: ${total_gross_removed:,.2f}")
    
    if len(groups) > 0:
        print(f"\nTop 10 Groups Being Cleaned:")
        print(f"{'Driver':<12} {'Date':<12} {'Amount':>12} {'Count':>6} {'Keep ID':>8} {'Delete IDs':<40}")
        print(f"{'-'*100}")
        
        for group in groups[:10]:
            keep_id = group['all_ids'][0]
            delete_ids = ', '.join(str(i) for i in group['ids_to_delete'][:5])
            if len(group['ids_to_delete']) > 5:
                delete_ids += '...'
            print(f"{group['driver_id']:<12} {str(group['pay_date']):<12} ${group['gross_pay']:>11,.2f} "
                  f"{group['dup_count']:>6} {keep_id:>8} {delete_ids:<40}")
    
    if dry_run:
        print(f"\n[WARN]  DRY RUN MODE - No changes made")
        print(f"Use --apply to execute the deletion")
        return 0
    
    if len(all_ids_to_delete) == 0:
        print(f"\nNo duplicates to delete")
        return 0
    
    # Execute deletion
    print(f"\nDeleting {len(all_ids_to_delete)} duplicate entries...")
    cur.execute("DELETE FROM driver_payroll WHERE id = ANY(%s)", (all_ids_to_delete,))
    deleted = cur.rowcount
    conn.commit()
    
    print(f"✓ Deleted {deleted:,} rows")
    
    return deleted

def main():
    parser = argparse.ArgumentParser(description='Remove duplicate payroll entries')
    parser.add_argument('--year', type=int, required=True, help='Year to clean')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Find duplicates
    print(f"\nScanning for duplicates in {args.year}...")
    groups = find_duplicate_groups(cur, args.year)
    
    if len(groups) == 0:
        print(f"No duplicates found for {args.year}")
        cur.close()
        conn.close()
        return
    
    # Create backup if applying
    if args.apply:
        backup_name = create_backup(cur, conn)
    
    # Delete duplicates
    deleted = delete_duplicates(cur, conn, groups, dry_run=not args.apply)
    
    if args.apply and deleted > 0:
        print(f"\n{'='*100}")
        print(f"VERIFICATION")
        print(f"{'='*100}")
        
        # Verify no duplicates remain
        remaining = find_duplicate_groups(cur, args.year)
        if len(remaining) > 0:
            print(f"[WARN]  WARNING: {len(remaining)} duplicate groups still remain!")
        else:
            print(f"✓ All duplicates successfully removed")
        
        # Show new totals
        has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
        date_col = 'pay_date' if has_pay_date else 'imported_at'
        
        query = f"""
        SELECT 
            COUNT(*) as entry_count,
            ROUND(SUM(gross_pay)::numeric, 2) as total_gross,
            ROUND(SUM(cpp)::numeric, 2) as total_cpp,
            ROUND(SUM(ei)::numeric, 2) as total_ei,
            ROUND(SUM(tax)::numeric, 2) as total_tax
        FROM driver_payroll
        WHERE {date_col} >= %s AND {date_col} < %s
        """
        
        if table_has_column(cur, 'driver_payroll', 'payroll_class'):
            query += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
        
        start = f"{args.year}-01-01"
        end = f"{args.year+1}-01-01"
        cur.execute(query, (start, end))
        row = cur.fetchone()
        
        print(f"\nNew {args.year} Totals:")
        print(f"  Entries:     {int(row[0]):>8,}")
        print(f"  Gross Pay:   ${float(row[1] or 0):>14,.2f}")
        print(f"  CPP:         ${float(row[2] or 0):>14,.2f}")
        print(f"  EI:          ${float(row[3] or 0):>14,.2f}")
        print(f"  Tax:         ${float(row[4] or 0):>14,.2f}")
        
        if args.apply:
            print(f"\n✓ Backup table: {backup_name}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

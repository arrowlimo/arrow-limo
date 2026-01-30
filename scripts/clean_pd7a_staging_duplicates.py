#!/usr/bin/env python3
"""Remove duplicate PD7A entries from staging table."""
import os, psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def find_duplicates(cur):
    """Find duplicate PD7A entries"""
    cur.execute("""
        SELECT 
            year,
            source_file,
            gross_payroll,
            COUNT(*) as dup_count,
            ARRAY_AGG(id ORDER BY id) as all_ids
        FROM staging_pd7a_year_end_summary
        GROUP BY year, source_file, gross_payroll, cpp_employee, ei_employee, 
                 tax_deductions, num_employees_paid
        HAVING COUNT(*) > 1
        ORDER BY year
    """)
    
    duplicates = []
    for row in cur.fetchall():
        duplicates.append({
            'year': row[0],
            'source_file': row[1],
            'gross_payroll': float(row[2] or 0),
            'dup_count': int(row[3]),
            'all_ids': row[4]
        })
    
    return duplicates

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Apply deletion')
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    duplicates = find_duplicates(cur)
    
    print(f"\n{'='*100}")
    print(f"PD7A STAGING DUPLICATE CLEANUP {'(DRY RUN)' if not args.apply else '(APPLYING)'}")
    print(f"{'='*100}\n")
    
    if not duplicates:
        print("No duplicates found")
        return
    
    total_to_delete = sum(d['dup_count'] - 1 for d in duplicates)
    
    print(f"Duplicate Groups: {len(duplicates)}")
    print(f"IDs to Delete: {total_to_delete}")
    
    print(f"\n{'Year':<6} {'Count':>6} {'Gross':>15} {'Keep ID':>8} {'Delete IDs':<40} Source")
    print(f"{'-'*120}")
    
    ids_to_delete = []
    for dup in duplicates:
        keep_id = dup['all_ids'][0]
        delete_ids = dup['all_ids'][1:]
        ids_to_delete.extend(delete_ids)
        
        source = dup['source_file'].split('\\')[-1] if dup['source_file'] else 'Unknown'
        delete_str = ', '.join(str(i) for i in delete_ids[:5])
        if len(delete_ids) > 5:
            delete_str += '...'
        
        print(f"{dup['year']:<6} {dup['dup_count']:>6} ${dup['gross_payroll']:>14,.2f} {keep_id:>8} {delete_str:<40} {source}")
    
    if not args.apply:
        print(f"\n[WARN]  DRY RUN - No changes made")
        print(f"Use --apply to delete duplicates")
        return
    
    # Execute deletion
    print(f"\nDeleting {len(ids_to_delete)} duplicate records...")
    cur.execute("DELETE FROM staging_pd7a_year_end_summary WHERE id = ANY(%s)", (ids_to_delete,))
    deleted = cur.rowcount
    conn.commit()
    
    print(f"✓ Deleted {deleted} rows")
    
    # Verify
    remaining = find_duplicates(cur)
    if remaining:
        print(f"[WARN]  WARNING: {len(remaining)} duplicate groups still remain")
    else:
        print(f"✓ All duplicates removed")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

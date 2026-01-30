#!/usr/bin/env python3
"""
Execute smart duplicate cleanup with recurring payment & NSF protection.
- Creates full backup before deletion
- Only deletes TRUE duplicates (same date, amount, vendor)
- Preserves recurring payments (same amount, different dates)
- Preserves NSF-only charges (never actually withdrawn)
"""

import psycopg2
from datetime import datetime
import argparse

def main():
    parser = argparse.ArgumentParser(description='Smart duplicate cleanup')
    parser.add_argument('--write', action='store_true', help='Actually delete duplicates')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted (default)')
    args = parser.parse_args()
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    if not args.write:
        print('DRY-RUN MODE (no changes will be made)')
        print('Add --write flag to execute deletion')
    print()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Step 1: Create backup if writing
    if args.write:
        print(f'Creating backup: receipts_smart_cleanup_backup_{timestamp}')
        cur.execute('''
            CREATE TABLE receipts_smart_cleanup_backup_{} AS
            SELECT * FROM receipts
        '''.format(timestamp))
        print(f'✅ Backup created with all {cur.rowcount:,} receipts')
        print()
    
    # Step 2: Build protected sets
    print('Building protected sets...')
    
    # Recurring payments
    RECURRING_KEYWORDS = ['RENT', 'LEASE', 'SUBSCRIPTION', 'MONTHLY', 'RECURRING', 
                          'MORTGAGE', 'INSURANCE', 'UTILITIES', 'PHONE', 'INTERNET']
    
    recurring_ids = set()
    for keyword in RECURRING_KEYWORDS:
        cur.execute('''
            SELECT receipt_id
            FROM receipts
            WHERE (vendor_name ILIKE %s OR description ILIKE %s)
        ''', (f'%{keyword}%', f'%{keyword}%'))
        for row in cur.fetchall():
            recurring_ids.add(row[0])
    
    print(f'  Recurring payments protected: {len(recurring_ids):,}')
    
    # NSF-only charges
    cur.execute('''
        SELECT DISTINCT r.receipt_id
        FROM receipts r
        WHERE (r.vendor_name LIKE '%NSF%' OR r.description LIKE '%NSF%')
        AND r.gross_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM receipts r2
            WHERE r2.receipt_date = r.receipt_date
            AND r2.gross_amount = -r.gross_amount
            AND (r2.vendor_name LIKE '%Customer Payment%')
        )
    ''')
    
    nsf_only_ids = set()
    for row in cur.fetchall():
        nsf_only_ids.add(row[0])
    
    print(f'  NSF-only charges protected: {len(nsf_only_ids):,}')
    print()
    
    # Step 3: Identify TRUE duplicates
    print('Identifying TRUE duplicates...')
    
    cur.execute('''
        SELECT 
            DATE(receipt_date) as receipt_date,
            gross_amount,
            vendor_name,
            COUNT(*) as count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
        FROM receipts
        WHERE NOT (
            vendor_name LIKE '%NSF%'
            OR vendor_name LIKE '%Customer Payment%'
            OR vendor_name LIKE '%NSF Event%'
        )
        GROUP BY DATE(receipt_date), gross_amount, vendor_name
        HAVING COUNT(*) > 1
    ''')
    
    delete_ids = set()
    dup_count = 0
    
    for date, amount, vendor, count, ids in cur.fetchall():
        ids_list = list(ids)
        
        # Skip if any are in protected sets
        recurring_count = sum(1 for id in ids_list if id in recurring_ids)
        nsf_only_count = sum(1 for id in ids_list if id in nsf_only_ids)
        
        if recurring_count > 0 or nsf_only_count > 0:
            continue
        
        # Mark for deletion (keep first)
        for delete_id in ids_list[1:]:
            delete_ids.add(delete_id)
        dup_count += 1
    
    print(f'Found {len(delete_ids):,} TRUE duplicates to delete')
    print(f'Across {dup_count:,} duplicate groups')
    print()
    
    if len(delete_ids) == 0:
        print('No TRUE duplicates found!')
        cur.close()
        conn.close()
        return
    
    # Step 4: Delete if --write
    if args.write:
        print('EXECUTING DELETION...')
        cur.execute('DELETE FROM receipts WHERE receipt_id = ANY(%s)', (list(delete_ids),))
        deleted_count = cur.rowcount
        conn.commit()
        print(f'✅ Deleted {deleted_count:,} duplicate receipts')
        print()
    else:
        print(f'Would delete {len(delete_ids):,} receipts (DRY-RUN)')
        print()
    
    # Step 5: Verify
    print('VERIFICATION:')
    cur.execute('SELECT COUNT(*) FROM receipts')
    total = cur.fetchone()[0]
    print(f'Total receipts remaining: {total:,}')
    
    cur.close()
    conn.close()
    print()
    print('✅ Smart duplicate cleanup complete')

if __name__ == '__main__':
    main()

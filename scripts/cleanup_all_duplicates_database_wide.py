#!/usr/bin/env python3
"""
Database-wide duplicate cleanup with NSF protection.
Removes 14,705 duplicate groups across all years (2007-2025).
"""

import psycopg2
from datetime import datetime
import hashlib

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('='*80)
print('DATABASE-WIDE DUPLICATE CLEANUP')
print('='*80)
print(f'Start Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Backup entire receipts table first
print('STEP 1: Creating backup of entire receipts table')
print('-'*80)

backup_table = f'receipts_backup_complete_20251205_{datetime.now().strftime("%H%M%S")}'

try:
    cur.execute(f'''
        CREATE TABLE {backup_table} AS
        SELECT * FROM receipts
    ''')
    conn.commit()
    
    cur.execute(f'SELECT COUNT(*) FROM {backup_table}')
    backup_count = cur.fetchone()[0]
    print(f'✅ Backup created: {backup_table} ({backup_count:,} rows)')
except Exception as e:
    print(f'❌ Backup failed: {e}')
    conn.rollback()
    cur.close()
    conn.close()
    exit(1)

print()

# Find all duplicates (same date, amount, vendor)
print('STEP 2: Identifying all duplicates with NSF protection')
print('-'*80)

cur.execute('''
    SELECT 
        receipt_id,
        DATE(receipt_date) as receipt_date,
        gross_amount,
        vendor_name,
        EXTRACT(YEAR FROM receipt_date) as year,
        ROW_NUMBER() OVER (PARTITION BY DATE(receipt_date), gross_amount, 
                          CASE WHEN vendor_name IS NULL THEN '' ELSE vendor_name END
                          ORDER BY receipt_id) as row_num
    FROM receipts
    WHERE NOT (
        vendor_name LIKE '%NSF%'
        OR vendor_name LIKE '%Customer Payment%'
        OR vendor_name LIKE '%NSF Event%'
        OR description LIKE '%NSF%'
        OR description LIKE '%NSF Event%'
    )
    ORDER BY receipt_date, gross_amount, receipt_id
''')

duplicates = cur.fetchall()

# Separate into keeps and deletes
keep_ids = set()
delete_ids = set()
dup_by_year = {}

for rec in duplicates:
    rec_id, date, amount, vendor, year, row_num = rec
    
    if row_num == 1:  # Keep first occurrence
        keep_ids.add(rec_id)
    else:  # Mark for deletion
        delete_ids.add(rec_id)
        if year not in dup_by_year:
            dup_by_year[year] = 0
        dup_by_year[year] += 1

print(f'Found {len(delete_ids)} duplicate receipts to delete')
print(f'Preserving {len(keep_ids)} first occurrences')
print()

# Show breakdown by year
if dup_by_year:
    print('Duplicates by year:')
    for year in sorted(dup_by_year.keys(), reverse=True):
        print(f'  {int(year)}: {dup_by_year[year]:,} duplicates')
    print()

# Step 3: Pre-verify deletion safety
print('STEP 3: Verifying deletion safety')
print('-'*80)

if delete_ids:
    cur.execute('''
        SELECT COUNT(*) FROM receipts WHERE receipt_id = ANY(%s)
    ''', (list(delete_ids),))
    
    verify_count = cur.fetchone()[0]
    print(f'Verified {verify_count:,} duplicate receipt IDs exist')
    
    if verify_count != len(delete_ids):
        print(f'⚠️  WARNING: Expected {len(delete_ids)} but found {verify_count}')
else:
    print('No duplicates found to delete')

print()

# Step 4: Execute deletion
print('STEP 4: Deleting duplicate receipts')
print('-'*80)

if delete_ids:
    try:
        cur.execute('''
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        ''', (list(delete_ids),))
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f'✅ Successfully deleted {deleted_count:,} duplicate receipts')
    except Exception as e:
        print(f'❌ Deletion failed: {e}')
        conn.rollback()
        cur.close()
        conn.close()
        exit(1)
else:
    print('No duplicates to delete')

print()

# Step 5: Verify results
print('STEP 5: Verifying cleanup results')
print('-'*80)

cur.execute('''
    SELECT COUNT(*) FROM receipts
''')
final_count = cur.fetchone()[0]

print(f'Final receipt count: {final_count:,}')
print()

# Count duplicates again
cur.execute('''
    SELECT COUNT(*) FROM (
        SELECT 1
        FROM receipts
        GROUP BY DATE(receipt_date), gross_amount, vendor_name
        HAVING COUNT(*) > 1
    ) dup
''')

remaining_dups = cur.fetchone()[0]
print(f'Remaining duplicate groups: {remaining_dups}')

if remaining_dups == 0:
    print('✅ All duplicates successfully removed!')
else:
    print(f'⚠️  {remaining_dups} duplicate groups still exist')

print()

# Step 6: NSF analysis
print('STEP 6: NSF Transaction Summary')
print('-'*80)

cur.execute('''
    SELECT 
        COUNT(*) as nsf_count,
        SUM(gross_amount) as total_nsf,
        COUNT(CASE WHEN gross_amount > 0 THEN 1 END) as charges,
        COUNT(CASE WHEN gross_amount < 0 THEN 1 END) as reversals
    FROM receipts
    WHERE (
        vendor_name LIKE '%NSF%'
        OR vendor_name LIKE '%Customer Payment%'
        OR vendor_name LIKE '%NSF Event%'
        OR description LIKE '%NSF%'
        OR description LIKE '%NSF Event%'
    )
''')

nsf_count, nsf_total, charges, reversals = cur.fetchone()

print(f'NSF-related transactions: {nsf_count:,}')
print(f'  Charges: {charges:,}')
print(f'  Reversals: {reversals:,}')
print(f'  Net NSF impact: ${float(nsf_total if nsf_total else 0):,.2f}')

print()

# Final stats
print('='*80)
print('CLEANUP COMPLETE')
print('='*80)
print()
print(f'Deleted: {len(delete_ids):,} duplicate receipts')
print(f'Remaining: {final_count:,} clean receipts')
print(f'Backup: {backup_table}')
print(f'End Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

print('NEXT STEPS:')
print('1. Verify data looks clean')
print('2. Regenerate all year-end Excel reports')
print('3. Reconcile banking matches')
print()

cur.close()
conn.close()

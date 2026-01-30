"""
Delete ALL bank fee duplicates across all years (2018-2025).
Keeps oldest receipt (lowest ID), deletes duplicates.
Total: 305 receipts to remove.
"""

import psycopg2
from datetime import datetime
import sys
sys.path.append('l:\\limo\\scripts')
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def find_bank_fee_duplicates():
    """Find all bank fee duplicates across all years."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as cnt,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids,
            MIN(receipt_id) as keep_id
        FROM receipts
        WHERE vendor_name LIKE 'Branch Transaction%'
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY receipt_date, vendor_name
    ''')
    
    duplicates = cur.fetchall()
    cur.close()
    conn.close()
    
    return duplicates

def analyze_duplicates(duplicates):
    """Analyze and display duplicate patterns."""
    print("=" * 100)
    print("BANK FEE DUPLICATES - ALL YEARS (2018-2025)")
    print("=" * 100)
    
    total_groups = len(duplicates)
    total_to_delete = sum(row[3] - 1 for row in duplicates)
    total_amount = sum(row[2] * (row[3] - 1) for row in duplicates)
    
    print(f'\nTotal duplicate groups: {total_groups}')
    print(f'Total receipts to delete: {total_to_delete}')
    print(f'Amount to remove: ${total_amount:,.2f}')
    
    # Group by fee type
    fee_types = {}
    for row in duplicates:
        fee_type = row[1]  # vendor_name
        if fee_type not in fee_types:
            fee_types[fee_type] = {'groups': 0, 'count': 0, 'amount': 0}
        fee_types[fee_type]['groups'] += 1
        fee_types[fee_type]['count'] += row[3] - 1
        fee_types[fee_type]['amount'] += row[2] * (row[3] - 1)
    
    print(f'\nBy fee type:')
    print(f'   Fee Type                                        | Groups | Count | Amount')
    print(f'   {"-" * 90}')
    for fee_type, stats in sorted(fee_types.items(), key=lambda x: x[1]['count'], reverse=True):
        fee_name = fee_type.replace('Branch Transaction ', '')[:45].ljust(45)
        print(f'   {fee_name} | {stats["groups"]:6} | {stats["count"]:5} | ${stats["amount"]:>10,.2f}')
    
    # Group by year
    year_stats = {}
    for row in duplicates:
        year = row[0].year
        if year not in year_stats:
            year_stats[year] = {'groups': 0, 'count': 0}
        year_stats[year]['groups'] += 1
        year_stats[year]['count'] += row[3] - 1
    
    print(f'\nBy year:')
    print(f'   Year | Groups | Count')
    print(f'   {"-" * 30}')
    for year in sorted(year_stats.keys()):
        stats = year_stats[year]
        print(f'   {year} | {stats["groups"]:6} | {stats["count"]:5}')
    
    # Show first 10 examples
    print(f'\nFirst 10 duplicate groups:')
    print(f'   Date       | Fee Type                                      | Amount   | Keep ID | Delete IDs')
    print(f'   {"-" * 100}')
    for row in duplicates[:10]:
        date = str(row[0])
        fee_type = row[1].replace('Branch Transaction ', '')[:45].ljust(45)
        keep_id = row[5]
        delete_ids = ', '.join(str(id) for id in row[4][1:])
        print(f'   {date} | {fee_type} | ${row[2]:>7,.2f} | {keep_id:7} | {delete_ids}')
    
    return total_to_delete, total_amount

def delete_duplicates(duplicates, dry_run=True):
    """Delete duplicate bank fee receipts."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Collect all IDs to delete (all except first/lowest ID in each group)
    all_delete_ids = []
    for row in duplicates:
        all_delete_ids.extend(row[4][1:])  # ids[1:] = all except first
    
    print(f'\n{"=" * 100}')
    if dry_run:
        print("DRY RUN - No changes will be made")
    else:
        print("EXECUTING DELETION")
    print("=" * 100)
    
    print(f'\nReceipts to delete: {len(all_delete_ids)}')
    print(f'ID range: {min(all_delete_ids)} to {max(all_delete_ids)}')
    
    if not dry_run:
        # Create backup
        print(f'\nCreating backup...')
        backup_name = create_backup_before_delete(
            cur, 
            'receipts', 
            condition=f"receipt_id IN ({','.join(str(id) for id in all_delete_ids)})"
        )
        print(f'Backup created: {backup_name}')
        
        # Delete from junction table first
        print(f'\nDeleting junction table links...')
        cur.execute('''
            DELETE FROM banking_receipt_matching_ledger
            WHERE receipt_id = ANY(%s)
        ''', (all_delete_ids,))
        junction_deleted = cur.rowcount
        print(f'Deleted {junction_deleted} junction table links')
        
        # Clear foreign key reference in banking_transactions
        print(f'\nClearing banking_transactions.receipt_id references...')
        cur.execute('''
            UPDATE banking_transactions
            SET receipt_id = NULL
            WHERE receipt_id = ANY(%s)
        ''', (all_delete_ids,))
        banking_updated = cur.rowcount
        print(f'Cleared {banking_updated} banking_transactions references')
        
        # Delete receipts
        print(f'\nDeleting receipts...')
        cur.execute('''
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        ''', (all_delete_ids,))
        receipts_deleted = cur.rowcount
        print(f'Deleted {receipts_deleted} receipts')
        
        conn.commit()
        
        # Log audit
        log_deletion_audit(
            'receipts', 
            receipts_deleted, 
            condition=f"Bank fee duplicates (kept oldest ID per group)"
        )
        
        print(f'\n✅ CLEANUP COMPLETE')
        print(f'   Deleted: {receipts_deleted} receipts')
        print(f'   Backup: {backup_name}')
    else:
        print(f'\n⚠️  DRY RUN - Run with --write to apply changes')
    
    cur.close()
    conn.close()
    
    return len(all_delete_ids)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Delete all bank fee duplicates (2018-2025)')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    print(f'\nAnalyzing bank fee duplicates...')
    duplicates = find_bank_fee_duplicates()
    
    if not duplicates:
        print('\n✅ No bank fee duplicates found!')
        return
    
    total_to_delete, total_amount = analyze_duplicates(duplicates)
    
    deleted = delete_duplicates(duplicates, dry_run=not args.write)
    
    print(f'\n{"=" * 100}')
    print(f'Session complete - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print("=" * 100)

if __name__ == '__main__':
    main()

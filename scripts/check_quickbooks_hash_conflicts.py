#!/usr/bin/env python3
"""
Check QuickBooks import data for source_hash conflicts with existing receipts.
"""

import psycopg2
import csv
import hashlib
import os
from decimal import Decimal

def get_source_hash(date_str, vendor_name, gross_amount, description):
    """Generate source hash same as import script.""" 
    hash_string = f"{date_str}|{vendor_name}|{gross_amount}|{description}"
    return hashlib.md5(hash_string.encode()).hexdigest()

def main():
    # Get existing hashes from database
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata', 
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    print('GETTING EXISTING SOURCE_HASH VALUES...')
    cur.execute('SELECT source_hash FROM receipts')
    existing_hashes = set(row[0] for row in cur.fetchall())
    print(f'Loaded {len(existing_hashes)} existing hashes from database')

    # Check QuickBooks data - using correct CSV structure
    qb_file = 'staging/2012_parsed/2012_quickbooks_transactions.csv'
    if not os.path.exists(qb_file):
        print(f'ERROR: QuickBooks file not found: {qb_file}')
        return

    print(f'\nCHECKING QUICKBOOKS DATA FOR CONFLICTS...')
    conflicts = []
    qb_hashes = set()
    duplicate_within_qb = []
    total_expense_records = 0

    with open(qb_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Filter to expense transactions (withdrawals)
            if row.get('withdrawal', '').strip() and float(row['withdrawal'] or 0) > 0:
                total_expense_records += 1
                
                # Prepare data same way as import script
                date_str = row['date']
                vendor_name = row['description'].strip()[:200]
                gross_amount = row['withdrawal']
                description = row['description'].strip()
                
                qb_hash = get_source_hash(date_str, vendor_name, gross_amount, description)
                
                # Check for conflict with existing database
                if qb_hash in existing_hashes:
                    conflicts.append((i+1, date_str, vendor_name, gross_amount, qb_hash[:16]))
                
                # Check for duplicates within QB data itself  
                if qb_hash in qb_hashes:
                    duplicate_within_qb.append((i+1, date_str, vendor_name, gross_amount, qb_hash[:16]))
                
                qb_hashes.add(qb_hash)

    print(f'\nRESULTS:')
    print(f'Total QB expense records processed: {total_expense_records}')
    print(f'Unique QB expense records: {len(qb_hashes)}')
    print(f'Conflicts with existing database: {len(conflicts)}')
    print(f'Duplicates within QB data: {len(duplicate_within_qb)}')

    if conflicts:
        print(f'\nFIRST 10 CONFLICTS WITH DATABASE:')
        for row_num, date, vendor, amount, hash_preview in conflicts[:10]:
            vendor_short = (vendor[:30] + '...') if vendor and len(vendor) > 30 else vendor or 'None'
            print(f'  Row {row_num}: {date} | {vendor_short} | ${amount} | Hash: {hash_preview}...')
            
        # Show what existing record has this hash
        for row_num, date, vendor, amount, hash_preview in conflicts[:3]:
            full_hash = get_source_hash(date, vendor, amount, vendor)  # description = vendor for QB data
            cur.execute('SELECT id, receipt_date, vendor_name, gross_amount, description FROM receipts WHERE source_hash = %s', (full_hash,))
            existing = cur.fetchone()
            if existing:
                existing_vendor = (existing[2][:30] + '...') if existing[2] and len(existing[2]) > 30 else existing[2] or 'None'
                existing_desc = (existing[4][:40] + '...') if existing[4] and len(existing[4]) > 40 else existing[4] or 'None'
                print(f'    -> Conflicts with DB record ID {existing[0]}: {existing[1]} | {existing_vendor} | ${existing[3]} | {existing_desc}')

    if duplicate_within_qb:
        print(f'\nFIRST 10 DUPLICATES WITHIN QB DATA:')
        for row_num, date, vendor, amount, hash_preview in duplicate_within_qb[:10]:
            vendor_short = (vendor[:30] + '...') if vendor and len(vendor) > 30 else vendor or 'None' 
            print(f'  Row {row_num}: {date} | {vendor_short} | ${amount} | Hash: {hash_preview}...')

    # Determine if we can proceed
    if conflicts:
        print(f'\n[FAIL] CANNOT IMPORT: {len(conflicts)} QuickBooks records conflict with existing database records')
        print('   These appear to be legitimate duplicate transactions that are already in the database.')
        print('   The import script needs to be modified to skip these conflicts.')
    elif duplicate_within_qb:
        print(f'\n[WARN]  WARNING: {len(duplicate_within_qb)} duplicate records within QuickBooks data')
        print('   These should be reviewed - may be legitimate separate transactions or true duplicates.')
    else:
        print(f'\n[OK] SAFE TO IMPORT: No hash conflicts detected')
        print(f'   All {len(qb_hashes)} QuickBooks records have unique hashes')

    conn.close()

if __name__ == '__main__':
    main()
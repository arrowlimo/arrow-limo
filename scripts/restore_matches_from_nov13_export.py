#!/usr/bin/env python3
"""
Restore payment-banking matches from November 13 JSON export backup.

The complete_almsdata_export.json file (1.06 GB) was created on Nov 13, 2025
BEFORE the data loss that wiped banking_transaction_id from payments.

This script:
1. Reads payments table from JSON export
2. Extracts payment_id → banking_transaction_id mappings
3. Compares to current database state
4. Restores lost matches (dry-run by default)

Usage:
    python scripts/restore_matches_from_nov13_export.py --dry-run
    python scripts/restore_matches_from_nov13_export.py --write
"""

import json
import gzip
import psycopg2
import argparse
from datetime import datetime

EXPORT_PATH = r"L:\limo\reports\complete_almsdata_export_20251113.json.gz"

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def load_payments_from_export():
    """Load payments table from JSON export (streaming to avoid memory issues)"""
    print(f"\n📂 Loading payments from {EXPORT_PATH}...")
    print("   (This may take a few minutes - compressed file is 51.8 MB)")
    
    with gzip.open(EXPORT_PATH, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check export metadata
    metadata = data.get('metadata', {})
    export_date = metadata.get('export_date', 'Unknown')
    total_rows = metadata.get('total_rows', 'Unknown')
    
    print(f"\n✅ Export loaded successfully")
    print(f"   Export date: {export_date}")
    print(f"   Total rows in export: {total_rows:,}")
    
    # Extract payments table
    tables = data.get('tables', {})
    payments_table = tables.get('payments', {})
    
    # Handle different export formats
    if isinstance(payments_table, list):
        # Already list of dicts
        payments_data = payments_table
    elif 'data' in payments_table:
        payments_data = payments_table['data']
    elif 'rows' in payments_table and 'schema' in payments_table:
        # Column-based format
        schema = payments_table['schema']
        rows = payments_table['rows']
        col_names = [col.get('name') if isinstance(col, dict) else str(col) for col in schema]
        
        # Convert to list of dicts
        payments_data = []
        for row in rows:
            if isinstance(row, dict):
                payments_data.append(row)
            elif isinstance(row, (list, tuple)):
                payment_dict = {}
                for i, val in enumerate(row):
                    if i < len(col_names):
                        payment_dict[col_names[i]] = val
                payments_data.append(payment_dict)
    else:
        # Assume it's a dict of payment_id -> data
        payments_data = list(payments_table.values()) if isinstance(payments_table, dict) else []
    
    print(f"   Payments in export: {len(payments_data):,}")
    
    return payments_data, export_date

def extract_banking_matches(payments_data):
    """Extract payment_id → banking_transaction_id mappings"""
    matches = {}
    reserve_numbers = {}
    
    for payment in payments_data:
        payment_id = payment.get('payment_id')
        banking_id = payment.get('banking_transaction_id')
        reserve = payment.get('reserve_number')
        
        if payment_id and banking_id:
            matches[payment_id] = banking_id
        
        if payment_id and reserve:
            reserve_numbers[payment_id] = reserve
    
    return matches, reserve_numbers

def get_current_matches(conn):
    """Get current payment-banking matches from database"""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            payment_id,
            banking_transaction_id,
            reserve_number,
            amount,
            payment_date
        FROM payments
        WHERE banking_transaction_id IS NOT NULL
    """)
    
    current = {}
    for pid, bid, reserve, amt, pdate in cur.fetchall():
        current[pid] = {
            'banking_id': bid,
            'reserve': reserve,
            'amount': amt,
            'date': pdate
        }
    
    cur.close()
    return current

def main():
    parser = argparse.ArgumentParser(description='Restore payment-banking matches from Nov 13 export')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Preview changes (default)')
    parser.add_argument('--write', action='store_true', help='Actually update database')
    args = parser.parse_args()
    
    if args.write:
        args.dry_run = False
    
    print("="*80)
    print("RESTORE PAYMENT-BANKING MATCHES FROM NOVEMBER 13, 2025 EXPORT")
    print("="*80)
    print(f"\nMode: {'✍️  WRITE (updating database)' if not args.dry_run else '🔍 DRY RUN (preview only)'}")
    
    # Load export
    payments_export, export_date = load_payments_from_export()
    
    # Extract matches
    print(f"\n📊 Extracting matches from export...")
    export_matches, export_reserves = extract_banking_matches(payments_export)
    
    print(f"   Payments with banking_transaction_id: {len(export_matches):,}")
    print(f"   Payments with reserve_number: {len(export_reserves):,}")
    
    # Connect to database
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Get current state
    print(f"\n📊 Checking current database state...")
    current_matches = get_current_matches(conn)
    print(f"   Current payments with banking_transaction_id: {len(current_matches):,}")
    
    # Find payments that need restoration
    print(f"\n🔍 Comparing export to current database...")
    
    can_restore = []
    already_matched = []
    conflict = []
    not_in_db = []
    
    cur.execute("SELECT payment_id FROM payments")
    current_payment_ids = set(row[0] for row in cur.fetchall())
    
    for payment_id, banking_id in export_matches.items():
        if payment_id not in current_payment_ids:
            not_in_db.append(payment_id)
            continue
        
        if payment_id in current_matches:
            if current_matches[payment_id]['banking_id'] == banking_id:
                already_matched.append(payment_id)
            else:
                conflict.append((payment_id, banking_id, current_matches[payment_id]['banking_id']))
        else:
            can_restore.append((payment_id, banking_id))
    
    print(f"\n📈 Analysis:")
    print(f"   Already correctly matched: {len(already_matched):,}")
    print(f"   Can restore (missing in DB): {len(can_restore):,}")
    print(f"   Conflicts (different banking_id): {len(conflict):,}")
    print(f"   Not in current DB: {len(not_in_db):,}")
    
    if conflict:
        print(f"\n⚠️  Sample conflicts (current vs export):")
        for pid, export_bid, current_bid in conflict[:10]:
            print(f"      Payment {pid}: Current={current_bid}, Export={export_bid}")
    
    # Restore missing matches
    if can_restore:
        print(f"\n💾 {'Would restore' if args.dry_run else 'Restoring'} {len(can_restore):,} payment-banking matches...")
        
        if args.dry_run:
            print(f"\n   Sample matches to restore (first 20):")
            for pid, bid in can_restore[:20]:
                reserve = export_reserves.get(pid, 'NULL')
                print(f"      Payment {pid} → Banking {bid} (Reserve: {reserve})")
            if len(can_restore) > 20:
                print(f"      ... and {len(can_restore) - 20:,} more")
        else:
            # Apply updates
            update_count = 0
            for pid, bid in can_restore:
                cur.execute("""
                    UPDATE payments
                    SET banking_transaction_id = %s
                    WHERE payment_id = %s
                """, (bid, pid))
                update_count += 1
                
                if update_count % 1000 == 0:
                    print(f"      Updated {update_count:,} payments...")
            
            conn.commit()
            print(f"\n✅ Committed {update_count:,} payment matches")
            
            # Verify new state
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(banking_transaction_id) as matched
                FROM payments
            """)
            total, matched = cur.fetchone()
            match_pct = (matched / total * 100) if total > 0 else 0
            
            print(f"\n📊 NEW DATABASE STATE:")
            print(f"   Total payments: {total:,}")
            print(f"   Matched to banking: {matched:,} ({match_pct:.1f}%)")
    else:
        print(f"\n✅ No matches need restoration - database is up to date with export")
    
    # Also check reserve_number restoration
    print(f"\n" + "="*80)
    print("RESERVE_NUMBER RESTORATION CHECK")
    print("="*80)
    
    cur.execute("SELECT payment_id, reserve_number FROM payments WHERE reserve_number IS NULL")
    missing_reserve = {row[0]: True for row in cur.fetchall()}
    
    can_restore_reserve = []
    for pid, reserve in export_reserves.items():
        if pid in missing_reserve and pid in current_payment_ids:
            can_restore_reserve.append((pid, reserve))
    
    print(f"\n   Payments missing reserve_number: {len(missing_reserve):,}")
    print(f"   Can restore from export: {len(can_restore_reserve):,}")
    
    if can_restore_reserve:
        print(f"\n💡 TIP: Run with --restore-reserves to also fix reserve_number linkage")
        print(f"      (Add this feature if needed)")
    
    cur.close()
    conn.close()
    
    print(f"\n" + "="*80)
    print("RESTORATION COMPLETE" if not args.dry_run else "DRY-RUN COMPLETE")
    print("="*80)
    
    if args.dry_run:
        print(f"\n💡 To apply changes, run with --write flag")

if __name__ == '__main__':
    main()

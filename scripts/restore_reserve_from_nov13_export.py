#!/usr/bin/env python3
"""
Restore reserve_number linkages from November 13, 2025 export.

The Nov 13 export has 25,356 reserve_numbers vs current 24,766 (lost 590).
This script restores the missing reserve_number data.

Usage:
    python scripts/restore_reserve_from_nov13_export.py --dry-run
    python scripts/restore_reserve_from_nov13_export.py --write
"""

import json
import gzip
import psycopg2

EXPORT_PATH = r"L:\limo\reports\complete_almsdata_export_20251113.json.gz"

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    
    if args.write:
        args.dry_run = False
    
    print("="*80)
    print("RESTORE RESERVE_NUMBER FROM NOVEMBER 13, 2025 EXPORT")
    print("="*80)
    print(f"\nMode: {'✍️  WRITE' if not args.dry_run else '🔍 DRY RUN'}")
    
    # Load export
    print(f"\n📂 Loading export...")
    with gzip.open(EXPORT_PATH, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    
    tables = data.get('tables', {})
    payments_table = tables.get('payments', {})
    
    # Extract payments
    if 'rows' in payments_table and 'schema' in payments_table:
        schema = payments_table['schema']
        rows = payments_table['rows']
        col_names = [col.get('name') if isinstance(col, dict) else str(col) for col in schema]
        
        payments_export = []
        for row in rows:
            if isinstance(row, dict):
                payments_export.append(row)
            elif isinstance(row, (list, tuple)):
                pmt = {col_names[i]: row[i] if i < len(row) else None for i in range(len(col_names))}
                payments_export.append(pmt)
    else:
        payments_export = list(payments_table.values()) if isinstance(payments_table, dict) else []
    
    print(f"   Loaded {len(payments_export):,} payments from export")
    
    # Extract reserve numbers
    export_reserves = {}
    for p in payments_export:
        pid = p.get('payment_id')
        reserve = p.get('reserve_number')
        if pid and reserve:
            export_reserves[pid] = reserve
    
    print(f"   Export has {len(export_reserves):,} reserve_numbers")
    
    # Connect to DB
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    # Get current state
    cur.execute("SELECT payment_id, reserve_number FROM payments WHERE reserve_number IS NULL")
    missing_reserve = {row[0]: True for row in cur.fetchall()}
    
    print(f"   Current DB: {len(missing_reserve):,} payments missing reserve_number")
    
    # Find restorable
    can_restore = []
    for pid, reserve in export_reserves.items():
        if pid in missing_reserve:
            can_restore.append((pid, reserve))
    
    print(f"\n✅ Can restore: {len(can_restore):,} reserve_numbers")
    
    if can_restore:
        if args.dry_run:
            print(f"\n   Sample (first 30):")
            for pid, reserve in can_restore[:30]:
                print(f"      Payment {pid} → Reserve {reserve}")
            if len(can_restore) > 30:
                print(f"      ... and {len(can_restore)-30:,} more")
        else:
            print(f"\n💾 Restoring...")
            for i, (pid, reserve) in enumerate(can_restore, 1):
                cur.execute("UPDATE payments SET reserve_number = %s WHERE payment_id = %s", (reserve, pid))
                if i % 100 == 0:
                    print(f"      Updated {i:,} payments...")
            
            conn.commit()
            print(f"\n✅ Committed {len(can_restore):,} reserve_number restorations")
            
            # Verify
            cur.execute("SELECT COUNT(*), COUNT(reserve_number) FROM payments")
            total, with_reserve = cur.fetchone()
            print(f"\n📊 NEW STATE:")
            print(f"   Total: {total:,}")
            print(f"   With reserve: {with_reserve:,} ({with_reserve/total*100:.1f}%)")
            print(f"   Missing: {total-with_reserve:,} ({(total-with_reserve)/total*100:.1f}%)")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)
    
    if args.dry_run:
        print(f"\n💡 Run with --write to apply")

if __name__ == '__main__':
    main()

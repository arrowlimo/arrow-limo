"""
Deduplicate Fibrenew receipts in the database.
Identifies duplicates based on date, amount, and vendor, keeping only one.
"""
import psycopg2
import hashlib
import argparse
from collections import defaultdict
import os

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

def generate_hash(date, vendor, amount):
    """Generate deterministic hash for receipt."""
    key = f"{date}|{vendor}|{amount:.2f}"
    return hashlib.sha256(key.encode('utf-8')).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Deduplicate Fibrenew receipts')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    parser.add_argument('--backup', action='store_true', help='Create backup before deletion')
    args = parser.parse_args()
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIBRENEW RECEIPT DEDUPLICATION")
    print("=" * 80)
    print()
    
    # Get all Fibrenew receipts
    cur.execute("""
        SELECT 
            receipt_id, receipt_date, vendor_name, 
            gross_amount, description, created_from_banking
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        ORDER BY receipt_date, receipt_id
    """)
    
    receipts = cur.fetchall()
    print(f"Total Fibrenew receipts: {len(receipts)}")
    print()
    
    # Group by hash
    hash_groups = defaultdict(list)
    for receipt in receipts:
        receipt_id, date, vendor, amount, desc, auto = receipt
        hash_key = generate_hash(date, vendor, amount)
        hash_groups[hash_key].append({
            'id': receipt_id,
            'date': date,
            'vendor': vendor,
            'amount': amount,
            'description': desc,
            'auto_created': auto
        })
    
    # Find duplicates
    duplicates = {k: v for k, v in hash_groups.items() if len(v) > 1}
    
    print(f"Unique receipts (by date+vendor+amount): {len(hash_groups)}")
    print(f"Duplicate groups: {len(duplicates)}")
    print()
    
    if not duplicates:
        print("No duplicates found!")
        cur.close()
        conn.close()
        return
    
    # Analyze duplicates
    total_duplicate_receipts = sum(len(v) - 1 for v in duplicates.values())
    duplicate_amount = sum((len(v) - 1) * v[0]['amount'] for v in duplicates.values())
    
    print(f"Duplicate receipts to remove: {total_duplicate_receipts}")
    print(f"Duplicate amount: ${duplicate_amount:,.2f}")
    print()
    
    # Show sample duplicates
    print("Sample duplicate groups (first 5):")
    print("-" * 80)
    for i, (hash_key, group) in enumerate(list(duplicates.items())[:5], 1):
        print(f"\nGroup {i}: {len(group)} receipts for {group[0]['date']} ${group[0]['amount']:.2f}")
        for receipt in group:
            auto_flag = " [AUTO]" if receipt['auto_created'] else ""
            desc = (receipt['description'] or '')[:40]
            print(f"  ID {receipt['id']:5}: {receipt['vendor'][:30]}{auto_flag} | {desc}")
    print()
    
    if not args.write:
        print("=" * 80)
        print("DRY RUN - Use --write to remove duplicates")
        print("Use --backup to create backup table before deletion")
        print("=" * 80)
        cur.close()
        conn.close()
        return
    
    # Create backup if requested
    if args.backup:
        from datetime import datetime
        backup_name = f"receipts_fibrenew_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Creating backup: {backup_name}")
        cur.execute(f"""
            CREATE TABLE {backup_name} AS
            SELECT * FROM receipts
            WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        """)
        print(f"Backup created: {backup_name} ({len(receipts)} rows)")
        print()
    
    # Delete duplicates (keep first one in each group)
    print("Removing duplicates...")
    deleted_count = 0
    
    for hash_key, group in duplicates.items():
        # Keep first receipt (usually the manual entry), delete the rest
        to_delete = [r['id'] for r in group[1:]]
        
        for receipt_id in to_delete:
            cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
            deleted_count += 1
    
    conn.commit()
    
    print(f"Deleted {deleted_count} duplicate receipts")
    print()
    
    # Verify
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
    """)
    row = cur.fetchone()
    
    print("=" * 80)
    print("VERIFICATION:")
    print(f"  Remaining receipts: {row[0]}")
    print(f"  Total amount: ${row[1]:,.2f}")
    print(f"  Removed: {deleted_count} duplicates (${duplicate_amount:,.2f})")
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

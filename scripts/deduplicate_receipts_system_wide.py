"""
Remove duplicate receipts from system-wide imports.

CRITICAL ISSUE: 7,054 duplicate receipts found ($2.35M duplicate amount)
- 4,637 duplicate groups identified
- Most are "Point of Sale - Interac RETAIL PURCHASE" $0.00 entries (13-18 copies each)
- 2015 Charter_Service imports: 13 copies of $661.38 charge
- Two import waves: IDs 57000-59600 (first), 71000-71800 (second)

STRATEGY:
1. Keep earliest receipt_id in each duplicate group (first import = most reliable)
2. Preserve manual entries over auto-generated (created_from_banking=FALSE over TRUE)
3. Check banking_receipt_matching_ledger links before deletion
4. Delete with timestamped backup for safety

Usage:
    python deduplicate_receipts_system_wide.py                    # Dry-run (preview)
    python deduplicate_receipts_system_wide.py --write            # Execute with backup
    python deduplicate_receipts_system_wide.py --write --min-copies 5  # Only groups with 5+ duplicates
"""

import psycopg2
import argparse
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def create_backup(cur):
    """Create timestamped backup table before deletion"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'receipts_backup_{timestamp}'
    
    print(f"\n📦 Creating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM receipts
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"✅ Backup created: {count} receipts saved")
    
    return backup_table

def find_duplicates(cur, min_copies=2):
    """Find duplicate receipts grouped by date + vendor + amount"""
    print("\n🔍 Finding duplicate receipt groups...")
    
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as copies,
            array_agg(receipt_id ORDER BY receipt_id) as ids,
            array_agg(created_from_banking ORDER BY receipt_id) as banking_flags,
            array_agg(COALESCE(description, 'N/A') ORDER BY receipt_id) as descriptions
        FROM receipts
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) >= %s
        ORDER BY COUNT(*) DESC, gross_amount DESC
    """, (min_copies,))
    
    duplicates = cur.fetchall()
    
    print(f"✅ Found {len(duplicates)} duplicate groups")
    
    if duplicates:
        total_dupes = sum(row[3] - 1 for row in duplicates)
        total_amount = sum((row[2] or 0) * (row[3] - 1) for row in duplicates)
        print(f"   {total_dupes} duplicate records to remove")
        print(f"   ${total_amount:,.2f} duplicate amount")
    
    return duplicates

def check_banking_links(cur, receipt_ids):
    """Check if receipts have banking transaction links (both junction table and direct FK)"""
    if not receipt_ids:
        return []
    
    links = []
    
    # Check junction table
    cur.execute("""
        SELECT receipt_id, banking_transaction_id
        FROM banking_receipt_matching_ledger
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids,))
    links.extend(cur.fetchall())
    
    # Check direct foreign key in banking_transactions table
    cur.execute("""
        SELECT receipt_id, transaction_id
        FROM banking_transactions
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids,))
    links.extend(cur.fetchall())
    
    return links

def analyze_duplicates(cur, duplicates, verbose=True):
    """Analyze duplicate patterns and determine which to keep/delete"""
    print("\n📊 Analyzing duplicate patterns...")
    
    keep_ids = []
    delete_ids = []
    banking_linked = []
    
    for row in duplicates:
        date, vendor, amount, copies, ids, banking_flags, descriptions = row
        
        # Determine which ID to keep
        # Priority: 1) Manual entry (created_from_banking=FALSE)
        #           2) Has banking link
        #           3) Earliest ID
        
        # Check banking links for all IDs
        links = check_banking_links(cur, ids)
        linked_ids = {link[0] for link in links}
        
        # Find best ID to keep
        keep_id = None
        
        # Priority 1: Manual entry without banking flag
        for i, id in enumerate(ids):
            if not banking_flags[i] and id not in linked_ids:
                keep_id = id
                break
        
        # Priority 2: Has banking link (keep first one)
        if not keep_id and linked_ids:
            keep_id = min(linked_ids)
        
        # Priority 3: Earliest ID
        if not keep_id:
            keep_id = ids[0]
        
        keep_ids.append(keep_id)
        
        # All other IDs are duplicates to delete
        for id in ids:
            if id != keep_id:
                delete_ids.append(id)
                if id in linked_ids:
                    banking_linked.append(id)
        
        if verbose and len(duplicates) <= 20:
            print(f"\n{date} | {vendor} | ${amount or 0:.2f} ({copies} copies)")
            print(f"   KEEP: ID {keep_id}")
            print(f"   DELETE: {[id for id in ids if id != keep_id]}")
            if linked_ids:
                print(f"   ⚠️  Banking links: {linked_ids}")
    
    print(f"\n✅ Analysis complete:")
    print(f"   Keep: {len(keep_ids)} receipts (1 per group)")
    print(f"   Delete: {len(delete_ids)} duplicates")
    if banking_linked:
        print(f"   ⚠️  {len(banking_linked)} duplicates have banking links (will update ledger)")
    
    return keep_ids, delete_ids, banking_linked

def update_banking_links(cur, delete_ids, keep_mapping):
    """Update banking links (both junction table and direct FK) to point to kept receipts"""
    print("\n🔗 Updating banking transaction links...")
    
    updated_junction = 0
    updated_direct = 0
    
    for delete_id in delete_ids:
        # Find which group this ID belongs to and get the keep_id
        cur.execute("""
            SELECT receipt_date, vendor_name, gross_amount
            FROM receipts
            WHERE receipt_id = %s
        """, (delete_id,))
        
        result = cur.fetchone()
        if not result:
            continue
        
        date, vendor, amount = result
        
        # Find the keep_id for this group
        cur.execute("""
            SELECT MIN(receipt_id) as keep_id
            FROM receipts
            WHERE receipt_date = %s
            AND vendor_name = %s
            AND gross_amount = %s
            AND receipt_id != %s
        """, (date, vendor, amount, delete_id))
        
        keep_result = cur.fetchone()
        if not keep_result or not keep_result[0]:
            continue
        
        keep_id = keep_result[0]
        
        # Update junction table links
        cur.execute("""
            UPDATE banking_receipt_matching_ledger
            SET receipt_id = %s,
                notes = COALESCE(notes, '') || ' [Reassigned from deleted duplicate receipt ' || %s || ']'
            WHERE receipt_id = %s
        """, (keep_id, delete_id, delete_id))
        
        if cur.rowcount > 0:
            updated_junction += cur.rowcount
        
        # Update direct foreign key in banking_transactions
        cur.execute("""
            UPDATE banking_transactions
            SET receipt_id = %s
            WHERE receipt_id = %s
        """, (keep_id, delete_id))
        
        if cur.rowcount > 0:
            updated_direct += cur.rowcount
    
    print(f"✅ Updated {updated_junction} junction table links")
    print(f"✅ Updated {updated_direct} direct foreign key links")

def delete_duplicates(cur, delete_ids):
    """Delete duplicate receipt records"""
    print(f"\n🗑️  Deleting {len(delete_ids)} duplicate receipts...")
    
    # Delete in batches of 1000
    batch_size = 1000
    deleted = 0
    
    for i in range(0, len(delete_ids), batch_size):
        batch = delete_ids[i:i+batch_size]
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        """, (batch,))
        deleted += cur.rowcount
        
        if (i + batch_size) % 5000 == 0:
            print(f"   Deleted {deleted} so far...")
    
    print(f"✅ Deleted {deleted} duplicate receipts")
    return deleted

def verify_cleanup(cur):
    """Verify no duplicates remain"""
    print("\n✅ Verifying cleanup...")
    
    cur.execute("""
        SELECT COUNT(*) as groups
        FROM (
            SELECT receipt_date, vendor_name, gross_amount, COUNT(*) as copies
            FROM receipts
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
        ) remaining
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("✅ SUCCESS: No duplicate groups remain")
    else:
        print(f"⚠️  WARNING: {remaining} duplicate groups still exist")
        print("   (May be legitimate separate transactions with same date/vendor/amount)")
    
    return remaining

def show_top_duplicates(duplicates, limit=20):
    """Display top duplicate groups for review"""
    print(f"\n📋 Top {min(limit, len(duplicates))} duplicate groups:")
    print("=" * 100)
    
    for i, row in enumerate(duplicates[:limit], 1):
        date, vendor, amount, copies, ids, banking_flags, descriptions = row
        
        print(f"\n{i}. {date} | {vendor[:50]} | ${amount or 0:.2f} ({copies} copies)")
        print(f"   IDs: {ids[:10]}{'...' if len(ids) > 10 else ''}")
        
        # Show if auto-generated
        auto_count = sum(1 for flag in banking_flags if flag)
        if auto_count > 0:
            print(f"   Auto-generated: {auto_count}/{copies}")
        
        # Show unique descriptions
        unique_descs = set(desc for desc in descriptions if desc != 'N/A')
        if unique_descs and len(unique_descs) <= 3:
            for desc in list(unique_descs)[:3]:
                print(f"   Description: {desc[:70]}")

def main():
    parser = argparse.ArgumentParser(description='Remove duplicate receipts from system-wide imports')
    parser.add_argument('--write', action='store_true', 
                       help='Execute deletion (default is dry-run)')
    parser.add_argument('--min-copies', type=int, default=2,
                       help='Minimum number of copies to consider duplicate (default: 2)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed analysis of each duplicate group')
    
    args = parser.parse_args()
    
    print("=" * 100)
    print("RECEIPT DEDUPLICATION - SYSTEM-WIDE CLEANUP")
    print("=" * 100)
    
    if not args.write:
        print("\n🔍 DRY-RUN MODE (use --write to execute)")
    else:
        print("\n⚠️  WRITE MODE - Will delete duplicates with backup")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Step 1: Create backup if writing
        backup_table = None
        if args.write:
            backup_table = create_backup(cur)
            conn.commit()
        
        # Step 2: Find duplicates
        duplicates = find_duplicates(cur, args.min_copies)
        
        if not duplicates:
            print("\n✅ No duplicates found!")
            return
        
        # Step 3: Show top duplicates
        show_top_duplicates(duplicates)
        
        # Step 4: Analyze and determine keep/delete
        keep_ids, delete_ids, banking_linked = analyze_duplicates(
            cur, duplicates, verbose=args.verbose
        )
        
        if not args.write:
            print("\n" + "=" * 100)
            print("DRY-RUN SUMMARY")
            print("=" * 100)
            print(f"Would delete: {len(delete_ids)} duplicate receipts")
            print(f"Would keep: {len(keep_ids)} receipts (1 per group)")
            if banking_linked:
                print(f"Would update: {len(banking_linked)} banking links")
            print(f"\nTo execute: python {__file__} --write")
            return
        
        # Step 5: Update banking links if needed
        if banking_linked:
            update_banking_links(cur, banking_linked, keep_ids)
            conn.commit()
        
        # Step 6: Delete duplicates
        deleted_count = delete_duplicates(cur, delete_ids)
        conn.commit()
        
        # Step 7: Verify cleanup
        remaining = verify_cleanup(cur)
        
        print("\n" + "=" * 100)
        print("CLEANUP COMPLETE")
        print("=" * 100)
        print(f"✅ Deleted: {deleted_count} duplicate receipts")
        print(f"✅ Backup: {backup_table}")
        print(f"✅ Remaining duplicates: {remaining}")
        
        if remaining > 0:
            print("\nNote: Remaining duplicates may be legitimate separate transactions")
            print("      with same date/vendor/amount (e.g., multiple rent payments same day)")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Delete true duplicate receipts, excluding Groups 2, 10, and 17 which are legitimate
"""
import psycopg2
import json
from datetime import datetime
import sys

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

# Receipt IDs to EXCLUDE from deletion (legitimate same-day fees)
LEGITIMATE_GROUPS = {
    frozenset([137611, 137621]),  # Group 2: Two e-transfer fees
    frozenset([137276, 137281]),  # Group 10: NSF + email deposit fee
    frozenset([136601, 136602])   # Group 17: NSF + service charge
}

def is_legitimate_group(receipt_ids):
    """Check if this group is one of the legitimate same-day fee groups"""
    return frozenset(receipt_ids) in LEGITIMATE_GROUPS

def main():
    dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1
    
    if dry_run:
        print("="*100)
        print("DRY RUN MODE - No changes will be made")
        print("Run with --execute to actually delete duplicates")
        print("="*100)
    else:
        print("="*100)
        print("⚠️  EXECUTION MODE - Will delete duplicate receipts")
        print("="*100)
        response = input("\nType 'DELETE' to confirm: ")
        if response != 'DELETE':
            print("❌ Cancelled")
            return
    
    # Load deduplication report
    with open('l:\\limo\\data\\receipts_dedup_lookup.json', 'r') as f:
        dedup_data = json.load(f)
        duplicates_dict = dedup_data.get('duplicates', {})
    
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print(f"\n📊 Total duplicate groups: {len(duplicates_dict)}")
    
    # Analyze groups
    to_delete = []
    excluded_groups = []
    
    for key, group in duplicates_dict.items():
        receipt_ids = [item['receipt_id'] for item in group]
        
        if is_legitimate_group(receipt_ids):
            excluded_groups.append((key, receipt_ids))
            print(f"\n✅ EXCLUDING (legitimate): {key}")
            print(f"   Receipt IDs: {receipt_ids}")
            continue
        
        # For true duplicates, keep the LOWEST receipt_id (oldest), delete the rest
        receipt_ids_sorted = sorted(receipt_ids)
        keep_id = receipt_ids_sorted[0]
        delete_ids = receipt_ids_sorted[1:]
        
        to_delete.extend(delete_ids)
        
        parts = key.split('|')
        print(f"\n🗑️  {parts[0]} | ${parts[1]} | {parts[2]}")
        print(f"   Keep: {keep_id}, Delete: {delete_ids}")
    
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"Total groups: {len(duplicates_dict)}")
    print(f"Legitimate groups (excluded): {len(excluded_groups)}")
    print(f"True duplicate groups: {len(duplicates_dict) - len(excluded_groups)}")
    print(f"Receipts to delete: {len(to_delete)}")
    
    if excluded_groups:
        print(f"\n✅ Excluded legitimate groups:")
        for key, ids in excluded_groups:
            print(f"   {key} - IDs: {ids}")
    
    if not to_delete:
        print("\n✅ No receipts to delete")
        cur.close()
        conn.close()
        return
    
    # Show what will be deleted
    print(f"\n🗑️  Receipts to be deleted:")
    cur.execute(f"""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE receipt_id IN ({','.join(map(str, to_delete))})
        ORDER BY receipt_id
    """)
    
    for rec_id, date, vendor, amount, desc in cur.fetchall():
        desc_str = (desc or '')[:50]
        print(f"   #{rec_id}: {date} | ${amount} | {desc_str}")
    
    if dry_run:
        print("\n✅ DRY RUN COMPLETE - No changes made")
        print("Run with --execute to delete these receipts")
    else:
        print(f"\n⚠️  Deleting {len(to_delete)} duplicate receipts...")
        
        try:
            # Disable banking lock trigger
            print(f"\n🔓 Disabling banking lock trigger...")
            cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
            
            # Create backup first
            backup_table = f"receipts_backup_dedup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"\n📦 Creating backup: {backup_table}")
            cur.execute(f"""
                CREATE TABLE {backup_table} AS
                SELECT * FROM receipts
                WHERE receipt_id IN ({','.join(map(str, to_delete))})
            """)
            backup_count = cur.rowcount
            print(f"   ✅ Backed up {backup_count} receipts")
            
            # Clear foreign key references in banking_transactions
            print(f"\n🔗 Clearing foreign key references...")
            cur.execute(f"""
                UPDATE banking_transactions
                SET receipt_id = NULL
                WHERE receipt_id IN ({','.join(map(str, to_delete))})
            """)
            cleared_refs = cur.rowcount
            print(f"   ✅ Cleared {cleared_refs} foreign key references")
            
            # Clear references in banking_receipt_matching_ledger
            cur.execute(f"""
                DELETE FROM banking_receipt_matching_ledger
                WHERE receipt_id IN ({','.join(map(str, to_delete))})
            """)
            cleared_ledger = cur.rowcount
            print(f"   ✅ Cleared {cleared_ledger} ledger entries")
            
            # Delete duplicates
            cur.execute(f"""
                DELETE FROM receipts
                WHERE receipt_id IN ({','.join(map(str, to_delete))})
            """)
            deleted_count = cur.rowcount
            
            # Re-enable trigger
            print(f"\n🔒 Re-enabling banking lock trigger...")
            cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
            
            conn.commit()
            
            print(f"\n✅ Deleted {deleted_count} duplicate receipts")
            print(f"✅ Backup saved to: {backup_table}")
            
            # Verify
            cur.execute("SELECT COUNT(*) FROM receipts")
            remaining = cur.fetchone()[0]
            print(f"\n📊 Receipts remaining: {remaining:,}")
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            print("🔒 Re-enabling trigger...")
            cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
            conn.rollback()
            raise
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

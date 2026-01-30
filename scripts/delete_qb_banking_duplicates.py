"""
Delete QB vs Banking duplicate receipts.

This removes auto-created banking receipts that duplicate existing QuickBooks receipts.
"""

import psycopg2
import pandas as pd
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    print("="*80)
    print("DELETE QB vs BANKING DUPLICATE RECEIPTS")
    print("="*80)
    
    # Load deletion list
    deletion_file = 'L:\\limo\\reports\\qb_banking_duplicates_to_delete.csv'
    if not os.path.exists(deletion_file):
        print(f"\n❌ File not found: {deletion_file}")
        print("Run find_qb_vs_banking_duplicates.py first")
        return
    
    df = pd.read_csv(deletion_file)
    receipt_ids = df['receipt_id'].tolist()
    
    print(f"\nLoaded {len(receipt_ids)} receipts to delete:")
    print(f"Total amount: ${df['amount'].sum():,.2f}")
    
    # Show what will be deleted
    print("\nReceipts to DELETE:")
    for idx, row in df.iterrows():
        print(f"  ID {row['receipt_id']}: {row['date']} | {row['vendor']} | ${row['amount']:.2f} | {row['source']}")
    
    # Connect to database
    print("\nConnecting to database...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Verify receipts exist
    print("\nVerifying receipts exist in database...")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, source_system
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_id
    """, (receipt_ids,))
    
    existing = cur.fetchall()
    print(f"Found {len(existing)} receipts in database (expected {len(receipt_ids)})")
    
    if len(existing) != len(receipt_ids):
        missing = set(receipt_ids) - {r[0] for r in existing}
        print(f"\n⚠️  WARNING: {len(missing)} receipts not found: {missing}")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted")
            return
    
    # Create backup
    print("\n" + "="*80)
    print("CREATING BACKUP")
    print("="*80)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'receipts_backup_qb_dedup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM receipts 
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids,))
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"✅ Backup created: {backup_table} ({backup_count} rows)")
    
    # Check for foreign key dependencies
    print("\n" + "="*80)
    print("CHECKING FOREIGN KEY DEPENDENCIES")
    print("="*80)
    
    # Check banking_receipt_matching_ledger
    cur.execute("""
        SELECT COUNT(*) FROM banking_receipt_matching_ledger
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids,))
    
    banking_links = cur.fetchone()[0]
    if banking_links > 0:
        print(f"⚠️  Found {banking_links} banking_receipt_matching_ledger links")
        print("These will be deleted first (cascade)")
    else:
        print("✅ No banking_receipt_matching_ledger links")
    
    # Final confirmation
    print("\n" + "="*80)
    print("FINAL CONFIRMATION")
    print("="*80)
    print(f"\nWill DELETE {len(receipt_ids)} receipts")
    print(f"Backup table: {backup_table}")
    print(f"Banking links to delete: {banking_links}")
    
    response = input("\nProceed with deletion? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted - no changes made")
        conn.rollback()
        return
    
    # Delete banking links first
    if banking_links > 0:
        print("\nDeleting banking_receipt_matching_ledger links...")
        cur.execute("""
            DELETE FROM banking_receipt_matching_ledger
            WHERE receipt_id = ANY(%s)
        """, (receipt_ids,))
        print(f"✅ Deleted {cur.rowcount} banking links")
    
    # Delete receipts
    print("\nDeleting receipts...")
    cur.execute("""
        DELETE FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids,))
    
    deleted_count = cur.rowcount
    print(f"✅ Deleted {deleted_count} receipts")
    
    # Commit
    conn.commit()
    
    # Verify deletion
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_receipts = cur.fetchone()[0]
    print(f"Total receipts after deletion: {total_receipts:,}")
    
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (receipt_ids,))
    
    remaining = cur.fetchone()[0]
    if remaining > 0:
        print(f"⚠️  WARNING: {remaining} receipts still exist!")
    else:
        print(f"✅ All {deleted_count} receipts successfully deleted")
    
    # Summary
    print("\n" + "="*80)
    print("DELETION COMPLETE")
    print("="*80)
    print(f"\n✅ Deleted {deleted_count} banking auto-created duplicate receipts")
    print(f"✅ Backup: {backup_table}")
    print(f"✅ Total receipts remaining: {total_receipts:,}")
    print(f"\nTo rollback: INSERT INTO receipts SELECT * FROM {backup_table};")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

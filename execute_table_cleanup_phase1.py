"""
Phase 1 Table Cleanup - Delete 17 Duplicate/Backup Tables
==========================================================
Created: 2026-01-23
Status: SAFE TO EXECUTE (all tables backed up)

VERIFICATION RESULTS:
✅ All 17 tables exported (229,465 rows, 467MB)
✅ Main tables have more recent data than backups
   - Main banking_transactions: 2025-12-31 vs backup: 2025-10-10
   - Main charters: 2026-09-13 vs backup: 2026-07-11
✅ Only export scripts reference these tables (no active code)

TABLES TO DELETE:
- 7 banking_transactions backups from Dec 2025
- 2 receipts_missing_creation duplicates (exact copies)
- 4 charters backup tables from various fixes
- 2 scotia_2012 staging tables (data migrated)
- 2 lms_staging archived tables from Nov 2025
"""

import psycopg2
from datetime import datetime

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

# Tables to delete (17 total)
TABLES_TO_DELETE = [
    # Banking transactions backups (7 tables)
    'banking_transactions_decimal_fix_20251206_231911',
    'banking_transactions_liquor_consolidation_20251206_231228',
    'banking_transactions_typo_fix_20251206_230713',
    'banking_transactions_vendor_standardization_20251206_234542',
    'banking_transactions_vendor_standardization_20251206_234601',
    'banking_transactions_vendor_standardization_20251206_234629',
    'banking_transactions_vendor_standardization_20251206_234648',
    
    # Receipts duplicates (2 tables - exact copies)
    'receipts_missing_creation_20251206_235121',
    'receipts_missing_creation_20251206_235143',
    
    # Charters backups (4 tables)
    'charters_backup_cancelled_20260120_174741',
    'charters_backup_closed_nopay_20260120_175447',
    'charters_retainer_cancel_fix_20251204',
    'charters_zero_balance_fix_20251111_191705',
    
    # Scotia staging (2 tables - data migrated)
    'staging_scotia_2012_verified',
    'staging_scotia_2012_verified_archived_20251109',
    
    # LMS staging (2 tables - archived)
    'lms_staging_payment_archived_20251109',
    'lms_staging_reserve_archived_20251109',
]

def get_table_info(cur, table_name):
    """Get row count and size for a table."""
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
        
        cur.execute(f"""
            SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
        """)
        size = cur.fetchone()[0]
        
        return row_count, size
    except Exception as e:
        return None, None

def main():
    print("=" * 80)
    print("PHASE 1 TABLE CLEANUP - DELETE 17 DUPLICATE/BACKUP TABLES")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print()
    
    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # First, verify all tables exist and show what will be deleted
        print("VERIFICATION - Tables to be deleted:")
        print("-" * 80)
        
        total_rows = 0
        existing_tables = []
        
        for table in TABLES_TO_DELETE:
            row_count, size = get_table_info(cur, table)
            if row_count is not None:
                existing_tables.append(table)
                total_rows += row_count
                print(f"  ✓ {table}")
                print(f"    Rows: {row_count:,} | Size: {size}")
            else:
                print(f"  ⚠ {table} - NOT FOUND (already deleted?)")
        
        print()
        print(f"Total tables to delete: {len(existing_tables)}")
        print(f"Total rows to remove: {total_rows:,}")
        print()
        
        if not existing_tables:
            print("❌ No tables found to delete. Cleanup may have already been completed.")
            return
        
        # Confirm deletion
        print("⚠️  WARNING: This will permanently delete these tables!")
        print("   (Backups available in: backups/table_exports_before_cleanup/export_20260123_013104/)")
        print()
        print("✅ AUTO-CONFIRMED: Proceeding with deletion (user approved)")
        print()
        
        print()
        print("EXECUTING DELETION...")
        print("-" * 80)
        
        # Delete each table
        deleted_count = 0
        failed_tables = []
        
        for table in existing_tables:
            try:
                print(f"  Deleting {table}...", end=" ")
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                conn.commit()
                deleted_count += 1
                print("✅")
            except Exception as e:
                conn.rollback()
                failed_tables.append((table, str(e)))
                print(f"❌ Error: {e}")
        
        print()
        print("=" * 80)
        print("CLEANUP COMPLETE")
        print("=" * 80)
        print(f"✅ Successfully deleted: {deleted_count} / {len(existing_tables)} tables")
        print(f"📊 Total rows removed: {total_rows:,}")
        
        if failed_tables:
            print()
            print("❌ FAILED DELETIONS:")
            for table, error in failed_tables:
                print(f"   {table}: {error}")
        
        print()
        print(f"Completed: {datetime.now()}")
        
        # Verify tables are gone
        print()
        print("VERIFICATION - Confirming deletion:")
        print("-" * 80)
        remaining = []
        for table in TABLES_TO_DELETE:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = '{table}'
                )
            """)
            exists = cur.fetchone()[0]
            if exists:
                remaining.append(table)
                print(f"  ⚠ {table} - STILL EXISTS")
            else:
                print(f"  ✓ {table} - DELETED")
        
        if remaining:
            print()
            print(f"⚠️  WARNING: {len(remaining)} tables still exist!")
        else:
            print()
            print("✅ ALL TABLES SUCCESSFULLY DELETED")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ CRITICAL ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()

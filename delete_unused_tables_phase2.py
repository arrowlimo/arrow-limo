"""
Delete 9 Unused Orphaned Tables (Phase 2 Cleanup)
==================================================
These tables are NOT used by the application:
- 5 snapshot tables (verification records)
- 3 report tables (calculated on-the-fly)
- 1 suppliers table (junk data from bad import)

Total: 1,353 rows of unused data
"""

import psycopg2
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

TABLES_TO_DELETE = [
    # Snapshot tables (5 tables, 5 rows total)
    'accounting_books_final_verification',
    'accounting_system_verification',
    'etransfer_accounting_assessment',
    'etransfer_analysis_results',
    'etransfer_fix_final_results',
    
    # Report tables (3 tables, 278 rows total)
    'balance_sheet',
    'profit_and_loss',
    'trial_balance',
    
    # Junk data (1 table, 784 rows)
    'suppliers',
]

def main():
    print("=" * 80)
    print("PHASE 2 CLEANUP - DELETE 9 UNUSED ORPHANED TABLES")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print()
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Show what will be deleted
        print("VERIFICATION - Tables to be deleted:")
        print("-" * 80)
        
        total_rows = 0
        
        for table in TABLES_TO_DELETE:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cur.fetchone()[0]
                total_rows += row_count
                
                cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))")
                size = cur.fetchone()[0]
                
                print(f"  ✓ {table:<45} {row_count:>6} rows | {size}")
            except Exception as e:
                print(f"  ⚠ {table:<45} ERROR: {e}")
        
        print()
        print(f"Total tables: {len(TABLES_TO_DELETE)}")
        print(f"Total rows to remove: {total_rows:,}")
        print()
        print("⚠️  These tables are NOT used by the application")
        print("   - App generates reports dynamically from source data")
        print("   - Suppliers table is junk data (bad spreadsheet import)")
        print()
        
        # Delete tables
        print("EXECUTING DELETION...")
        print("-" * 80)
        
        deleted_count = 0
        
        for table in TABLES_TO_DELETE:
            try:
                print(f"  Deleting {table}...", end=" ")
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                conn.commit()
                deleted_count += 1
                print("✅")
            except Exception as e:
                conn.rollback()
                print(f"❌ Error: {e}")
        
        print()
        print("=" * 80)
        print("CLEANUP COMPLETE")
        print("=" * 80)
        print(f"✅ Successfully deleted: {deleted_count} / {len(TABLES_TO_DELETE)} tables")
        print(f"📊 Total rows removed: {total_rows:,}")
        
        # Verify deletion
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
        
        # Show final database stats
        print()
        print("FINAL DATABASE STATISTICS:")
        print("-" * 80)
        
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        table_count = cur.fetchone()[0]
        
        cur.execute("SELECT pg_size_pretty(pg_database_size('almsdata'))")
        db_size = cur.fetchone()[0]
        
        print(f"Total tables: {table_count} (was 307, deleted 9)")
        print(f"Database size: {db_size}")
        
        print()
        print(f"Completed: {datetime.now()}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ CRITICAL ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()

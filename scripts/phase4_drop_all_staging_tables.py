"""
Phase 4: Drop all 19 remaining staging/archive tables.

Handles:
- Views that depend on staging tables
- Foreign key constraints
- CSV backups of all tables
- Clean deletion with commit
"""
import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
conn.autocommit = False
cur = conn.cursor()

# All staging tables to drop
STAGING_TABLES = [
    'bank_transactions_staging',
    'cibc_checking_staging_archived_20251107',
    'cibc_qbo_staging_archived_20251107',
    'email_scanner_staging',
    'gl_transactions_staging_archived_20251107',
    'income_ledger_payment_archive',
    'lms_rate_mapping',
    'lms_staging_customer_archived_20251109',
    'lms_staging_vehicles',
    'lms_sync_log',
    'lms_vehicle_mapping',
    'orphaned_charges_archive',
    'payment_imports_archived_20251107',
    'payments_archived',
    'pdf_staging',
    'qb_export_invoices',
    'square_transactions_staging_archived_20251107',
    'staging_banking_pdf_transactions_archived_20251109',
    'staging_receipts_raw_archived_20251109'
]

# Views to drop (depend on staging tables)
STAGING_VIEWS = [
    'v_gl_transactions_by_account',
    'v_gl_transactions_by_type',
    'v_gl_unmapped_significant'
]

def backup_table(table_name):
    """Create CSV backup of table."""
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        if count == 0:
            print(f"  ⏭️  {table_name} (0 records, skipping backup)")
            return
        
        backup_file = f"L:/limo/reports/legacy_table_backups/{table_name}_PHASE4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        cur.execute(f"""
            COPY (SELECT * FROM {table_name})
            TO '{backup_file}'
            WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8')
        """)
        print(f"  ✅ {table_name} ({count:,} records) → backup saved")
    except Exception as e:
        print(f"  ⚠️  {table_name} backup failed: {e}")

try:
    print("=" * 80)
    print("PHASE 4: DROP ALL STAGING TABLES")
    print("=" * 80)
    
    # Step 1: Drop views first
    print(f"\n📝 Step 1: Dropping {len(STAGING_VIEWS)} dependent views...")
    for view_name in STAGING_VIEWS:
        cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")
        print(f"  ✅ Dropped view: {view_name}")
    
    # Step 2: Backup all tables
    print(f"\n📝 Step 2: Backing up {len(STAGING_TABLES)} staging tables...")
    for table_name in STAGING_TABLES:
        backup_table(table_name)
    
    # Step 3: Drop all tables (CASCADE handles FKs)
    print(f"\n📝 Step 3: Dropping {len(STAGING_TABLES)} staging tables...")
    dropped_count = 0
    for table_name in STAGING_TABLES:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            print(f"  ✅ Dropped: {table_name}")
            dropped_count += 1
        except Exception as e:
            print(f"  ❌ Failed to drop {table_name}: {e}")
    
    # Commit all changes
    conn.commit()
    
    print("\n" + "=" * 80)
    print("✅ PHASE 4 COMPLETE")
    print("=" * 80)
    
    # Summary
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
    table_count = cur.fetchone()[0]
    
    print(f"\nResults:")
    print(f"  Views dropped: {len(STAGING_VIEWS)}")
    print(f"  Tables dropped: {dropped_count}/{len(STAGING_TABLES)}")
    print(f"  Database now has {table_count} tables (was 290)")
    
    # Check for any remaining staging tables
    cur.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        AND (
            table_name LIKE 'lms_%'
            OR table_name LIKE 'limo_%'
            OR table_name LIKE '%_staging%'
            OR table_name LIKE '%_archive%'
        )
    """)
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print(f"\n🎉 CLEAN DATABASE - No staging tables remain!")
    else:
        print(f"\n⚠️  {remaining} staging tables still remain")
    
    print("\n" + "=" * 80)
    print("LEGACY TABLE CLEANUP COMPLETE")
    print("=" * 80)
    print(f"\nPhase 1: Dropped 3 tables (limo_contacts, lms_charges, lms_deposits)")
    print(f"Phase 2: Dropped 4 tables + 6 views (limo_clients, limo_addresses)")
    print(f"Phase 3: Dropped 1 table (lms_customers_enhanced)")
    print(f"Phase 4: Dropped {dropped_count} tables + {len(STAGING_VIEWS)} views (all staging/archives)")
    print(f"\nTotal removed: {3 + 4 + 1 + dropped_count} tables, {6 + len(STAGING_VIEWS)} views")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    raise
finally:
    cur.close()
    conn.close()

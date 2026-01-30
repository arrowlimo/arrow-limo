#!/usr/bin/env python3
"""
Execute database table cleanup - Drop 35 unused empty tables
"""
import psycopg2
from datetime import datetime

# List of tables to drop (35 tables confirmed empty and unused)
TABLES_TO_DROP = [
    # Redundant systems (3)
    'bookings',
    'payment_reconciliation',
    'invoices',
    
    # Audit & Logging (2)
    'audit_log',
    'audit_trail',
    
    # Vehicle management (4)
    'vehicle_assignments',
    'vehicle_fleet_history',
    'vehicle_odometer_log',
    'vehicle_registration',
    
    # Financial tracking (9)
    'deposits',
    'cash_box_ledger',
    'budget_vs_actual',
    'financial_statements',
    'financial_statement_mapping',
    'tax_transactions',
    'accounts_receivable',
    'asset_depreciation_schedule',
    'bad_debt_log',
    
    # Payroll (2)
    'employee_payments',
    'accounting_payroll',
    
    # Operations (2)
    'trip_financial_transactions',
    'chauffeur_payment_matches',
    
    # Scheduling (1)
    'maintenance_schedules',
    
    # System features (7)
    'refresh_tokens',
    'file_processing_queue',
    'etransfer_exclusions',
    'period_closures',
    'posting_controls',
    'batch_sessions',
    'schema_backups',
    
    # Reconciliation (2)
    'square_reconciliation',
    'financial_reconciliation_status',
]

# Tables we're KEEPING (should NOT drop)
TABLES_TO_KEEP = [
    'maintenance_records',      # Need to implement maintenance system
    'vehicle_documents',        # Need PDF storage system
    'vehicle_fuel_log',         # Need per-vehicle fuel tracking
    'vehicle_insurance',        # Need insurance policy tracking
    'qb_excel_staging',         # QuickBooks imports
    'staging_t4_validation',    # T4 imports
]

def main():
    print("=" * 80)
    print("DATABASE TABLE CLEANUP EXECUTION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTables to drop: {len(TABLES_TO_DROP)}")
    print(f"Tables to keep: {len(TABLES_TO_KEEP)}")
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    
    # First, verify all tables are empty
    print("\n" + "-" * 80)
    print("STEP 1: Verifying all tables are empty")
    print("-" * 80)
    
    cur = conn.cursor()
    non_empty = []
    
    for table in TABLES_TO_DROP:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            if count > 0:
                non_empty.append((table, count))
                print(f"  WARNING: {table} has {count} rows!")
            else:
                print(f"  OK: {table} (0 rows)")
        except psycopg2.errors.UndefinedTable:
            print(f"  SKIP: {table} (doesn't exist)")
            conn.rollback()
        except Exception as e:
            print(f"  ERROR: {table} - {e}")
            conn.rollback()
    
    if non_empty:
        print("\n" + "!" * 80)
        print("ABORT: Found non-empty tables!")
        print("!" * 80)
        for table, count in non_empty:
            print(f"  {table}: {count} rows")
        print("\nNot dropping any tables. Please review.")
        conn.close()
        return
    
    # Get count before cleanup
    print("\n" + "-" * 80)
    print("STEP 2: Getting table counts before cleanup")
    print("-" * 80)
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE'
    """)
    tables_before = cur.fetchone()[0]
    print(f"  Total tables before: {tables_before}")
    
    cur.execute("SELECT pg_size_pretty(pg_database_size('almsdata'))")
    size_before = cur.fetchone()[0]
    print(f"  Database size before: {size_before}")
    
    # Execute drops
    print("\n" + "-" * 80)
    print("STEP 3: Dropping tables")
    print("-" * 80)
    
    dropped_count = 0
    skipped_count = 0
    error_count = 0
    
    for table in TABLES_TO_DROP:
        try:
            print(f"  Dropping {table}...", end=" ")
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            conn.commit()
            print("OK")
            dropped_count += 1
        except Exception as e:
            print(f"ERROR: {e}")
            conn.rollback()
            error_count += 1
    
    # Get count after cleanup
    print("\n" + "-" * 80)
    print("STEP 4: Verifying cleanup")
    print("-" * 80)
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE'
    """)
    tables_after = cur.fetchone()[0]
    print(f"  Total tables after: {tables_after}")
    print(f"  Tables removed: {tables_before - tables_after}")
    
    # Verify kept tables still exist
    print("\n" + "-" * 80)
    print("STEP 5: Verifying kept tables still exist")
    print("-" * 80)
    
    for table in TABLES_TO_KEEP:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  OK: {table} exists ({count} rows)")
        except psycopg2.errors.UndefinedTable:
            print(f"  WARNING: {table} doesn't exist")
            conn.rollback()
    
    # VACUUM to reclaim space
    print("\n" + "-" * 80)
    print("STEP 6: Reclaiming disk space (VACUUM)")
    print("-" * 80)
    
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur.execute("VACUUM ANALYZE")
    print("  VACUUM ANALYZE complete")
    
    cur.execute("SELECT pg_size_pretty(pg_database_size('almsdata'))")
    size_after = cur.fetchone()[0]
    print(f"  Database size after: {size_after}")
    
    # Summary
    print("\n" + "=" * 80)
    print("CLEANUP SUMMARY")
    print("=" * 80)
    print(f"  Successfully dropped: {dropped_count} tables")
    print(f"  Errors: {error_count} tables")
    print(f"  Tables before: {tables_before}")
    print(f"  Tables after: {tables_after}")
    print(f"  Database size before: {size_before}")
    print(f"  Database size after: {size_after}")
    print(f"\n  Kept for future use:")
    for table in TABLES_TO_KEEP:
        print(f"    - {table}")
    
    print("\n" + "=" * 80)
    print("CLEANUP COMPLETE!")
    print("=" * 80)
    
    conn.close()

if __name__ == "__main__":
    main()

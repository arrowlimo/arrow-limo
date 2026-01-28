#!/usr/bin/env python
"""
Run database migrations for booking lifecycle (Steps 2B-7)
Date: 2026-01-22
"""

import os
import psycopg2
from psycopg2 import sql

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

MIGRATIONS = [
    "20260122_step2b_driver_hos_pay.sql",
    "20260122_step2b_effective_hourly_trigger.sql",
    "20260122_step3_dispatch.sql",
    "20260122_step4_service_execution.sql",
    "20260122_step5_completion_closeout.sql",
    "20260122_step6_invoice_payment.sql",
    "20260122_step7_archive_records.sql",
]

def run_migration(conn, migration_file):
    """Execute a single migration file"""
    filepath = f"migrations/{migration_file}"
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    try:
        with open(filepath, 'r') as f:
            sql_content = f.read()
        
        cursor = conn.cursor()
        cursor.execute(sql_content)
        conn.commit()
        cursor.close()
        
        print(f"✅ {migration_file}")
        return True
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ {migration_file}")
        print(f"   Error: {e}")
        return False

def verify_tables(conn):
    """Check if key tables were created"""
    cursor = conn.cursor()
    
    expected_tables = [
        'charter_driver_pay',
        'hos_log',
        'charter_beverage_orders',
        'dispatch_events',
        'charter_incidents',
        'customer_feedback',
        'invoices',
    ]
    
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = ANY(%s)
    """, (expected_tables,))
    
    found = {row[0] for row in cursor.fetchall()}
    missing = set(expected_tables) - found
    
    cursor.close()
    
    if missing:
        print(f"\n⚠️  Missing tables: {missing}")
        return False
    else:
        print(f"\n✅ All {len(expected_tables)} key tables created")
        return True

def verify_views(conn):
    """Check if key views were created"""
    cursor = conn.cursor()
    
    expected_views = [
        'v_revenue_summary',
        'v_driver_pay_summary',
        'v_vehicle_utilization',
        'v_incident_trends',
        'v_hos_compliance_summary',
        'v_outstanding_receivables',
    ]
    
    cursor.execute("""
        SELECT table_name FROM information_schema.views 
        WHERE table_schema = 'public' AND table_name = ANY(%s)
    """, (expected_views,))
    
    found = {row[0] for row in cursor.fetchall()}
    missing = set(expected_views) - found
    
    cursor.close()
    
    if missing:
        print(f"⚠️  Missing views: {missing}")
        return False
    else:
        print(f"✅ All {len(expected_views)} reporting views created")
        return True

def main():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print(f"Connected to {DB_NAME} @ {DB_HOST}\n")
        print("Running migrations...\n")
        
        failed = []
        for migration in MIGRATIONS:
            if not run_migration(conn, migration):
                failed.append(migration)
        
        if failed:
            print(f"\n❌ {len(failed)} migration(s) failed:")
            for f in failed:
                print(f"   - {f}")
            return 1
        
        print(f"\n✅ All {len(MIGRATIONS)} migrations applied successfully")
        
        # Verify tables and views
        verify_tables(conn)
        verify_views(conn)
        
        conn.close()
        print("\n✅ Migration validation complete")
        return 0
        
    except psycopg2.Error as e:
        print(f"❌ Connection error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())

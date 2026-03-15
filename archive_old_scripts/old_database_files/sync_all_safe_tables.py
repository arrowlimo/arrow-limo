#!/usr/bin/env python3
"""
SYNC ALL SAFE TABLES TO NEON
==============================

Syncs all 15 verified-safe tables to Neon database.
These tables either don't exist in Neon or are empty.
"""

import os
import subprocess
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Database credentials
LOCAL_HOST = "localhost"
LOCAL_DB = os.environ.get("LOCAL_DB_NAME", "almsdata")
LOCAL_USER = os.environ.get("LOCAL_DB_USER", "alms")
LOCAL_PASSWORD = os.environ.get("LOCAL_DB_PASSWORD", "")

NEON_HOST = os.environ.get("NEON_DB_HOST", "")
NEON_DB = os.environ.get("NEON_DB_NAME", "neondb")
NEON_USER = os.environ.get("NEON_DB_USER", "neondb_owner")
NEON_PASSWORD = os.environ.get("NEON_DB_PASSWORD", "")

# All 15 safe tables
SAFE_TABLES = [
    # Original 6 tables
    "beverage_products",
    "lms2026_payment_matches",
    "charter_gst_details_2010_2012",
    "employee_t4_records",
    "employee_t4_summary",
    "alcohol_business_tracking",
    # Newly verified 9 tables
    "employee_pay_master",
    "transaction_categories",
    "transaction_subcategories",
    "tax_periods",
    "tax_returns",
    "tax_variances",
    "category_mappings",
    "account_categories",
    "category_to_account_map",
]

sync_results = {
    "timestamp": datetime.now().isoformat(),
    "tables_synced": [],
    "tables_failed": [],
    "total_rows_synced": 0
}


def export_table(table):
    """Export a single table using pg_dump."""
    print(f"\n📤 Exporting {table}...", end=" ", flush=True)
    
    export_file = f"temp_{table}_export.sql"
    
    try:
        cmd = [
            "pg_dump",
            "-h", LOCAL_HOST,
            "-U", LOCAL_USER,
            "-d", LOCAL_DB,
            "-t", table,
            "--schema=public",
            "--clean",
            "--if-exists",
            "-f", export_file
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = LOCAL_PASSWORD
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FAILED")
            print(f"   Error: {result.stderr}")
            return None
        
        # Check file size
        size = os.path.getsize(export_file)
        print(f"✅ ({size:,} bytes)")
        return export_file
        
    except Exception as e:
        print(f"❌ FAILED")
        print(f"   Exception: {e}")
        return None


def import_to_neon(table, export_file):
    """Import table to Neon using psql."""
    print(f"📥 Importing {table} to Neon...", end=" ", flush=True)
    
    try:
        cmd = [
            "psql",
            "-h", NEON_HOST,
            "-U", NEON_USER,
            "-d", NEON_DB,
            "-f", export_file
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = NEON_PASSWORD
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FAILED")
            print(f"   Error: {result.stderr}")
            return False
        
        print(f"✅ SUCCESS")
        return True
        
    except Exception as e:
        print(f"❌ FAILED")
        print(f"   Exception: {e}")
        return False


def verify_sync(table):
    """Verify sync by comparing row counts."""
    print(f"🔍 Verifying {table}...", end=" ", flush=True)
    
    try:
        # Get local count
        local_conn = psycopg2.connect(
            host=LOCAL_HOST,
            database=LOCAL_DB,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD
        )
        local_cur = local_conn.cursor()
        local_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        local_count = local_cur.fetchone()[0]
        local_cur.close()
        local_conn.close()
        
        # Get Neon count
        neon_conn = psycopg2.connect(
            host=NEON_HOST,
            database=NEON_DB,
            user=NEON_USER,
            password=NEON_PASSWORD,
            sslmode='require'
        )
        neon_cur = neon_conn.cursor()
        neon_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        neon_count = neon_cur.fetchone()[0]
        neon_cur.close()
        neon_conn.close()
        
        if local_count == neon_count:
            print(f"✅ MATCHED ({neon_count:,} rows)")
            sync_results["total_rows_synced"] += neon_count
            return True
        else:
            print(f"⚠️ MISMATCH (Local: {local_count:,}, Neon: {neon_count:,})")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def cleanup_export_files():
    """Remove temporary export files."""
    print("\n🧹 Cleaning up temporary files...")
    cleaned = 0
    for table in SAFE_TABLES:
        export_file = f"temp_{table}_export.sql"
        if os.path.exists(export_file):
            os.remove(export_file)
            cleaned += 1
    print(f"   Removed {cleaned} temporary files")


def sync_table(table):
    """Sync a single table."""
    print(f"\n{'=' * 80}")
    print(f"SYNCING: {table}")
    print(f"{'=' * 80}")
    
    # Export
    export_file = export_table(table)
    if not export_file:
        sync_results["tables_failed"].append({
            "table": table,
            "stage": "export",
            "error": "Export failed"
        })
        return False
    
    # Import
    if not import_to_neon(table, export_file):
        sync_results["tables_failed"].append({
            "table": table,
            "stage": "import",
            "error": "Import failed"
        })
        return False
    
    # Verify
    if not verify_sync(table):
        sync_results["tables_failed"].append({
            "table": table,
            "stage": "verify",
            "error": "Verification failed"
        })
        return False
    
    sync_results["tables_synced"].append(table)
    return True


def print_summary():
    """Print sync summary."""
    print(f"\n{'=' * 80}")
    print("SYNC SUMMARY")
    print(f"{'=' * 80}")
    
    print(f"\n✅ Successfully synced: {len(sync_results['tables_synced'])} tables")
    for table in sync_results["tables_synced"]:
        print(f"   • {table}")
    
    if sync_results["tables_failed"]:
        print(f"\n❌ Failed: {len(sync_results['tables_failed'])} tables")
        for failed in sync_results["tables_failed"]:
            print(f"   • {failed['table']} ({failed['stage']}: {failed['error']})")
    
    print(f"\n📊 Total rows synced: {sync_results['total_rows_synced']:,}")
    print(f"⏱️  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Run the sync."""
    print("=" * 80)
    print("SYNC ALL SAFE TABLES TO NEON")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nWill sync {len(SAFE_TABLES)} tables to Neon cloud database")
    print("=" * 80)
    
    # Confirm
    print("\n⚠️  This will sync the following tables:")
    for i, table in enumerate(SAFE_TABLES, 1):
        print(f"   {i:2}. {table}")
    
    response = input("\nProceed with sync? (yes/no): ").strip().lower()
    if response != 'yes':
        print("\n❌ Sync cancelled by user")
        return
    
    print(f"\n🚀 Starting sync of {len(SAFE_TABLES)} tables...")
    
    # Sync each table
    success_count = 0
    for table in SAFE_TABLES:
        if sync_table(table):
            success_count += 1
    
    # Cleanup
    cleanup_export_files()
    
    # Summary
    print_summary()
    
    if success_count == len(SAFE_TABLES):
        print("\n🎉 All tables synced successfully!")
    else:
        print(f"\n⚠️  {len(SAFE_TABLES) - success_count} tables failed to sync")


if __name__ == "__main__":
    main()

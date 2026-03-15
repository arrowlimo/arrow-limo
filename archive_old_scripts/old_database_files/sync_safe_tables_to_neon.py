#!/usr/bin/env python3
"""
SAFE TABLE SYNC TO NEON
========================

Syncs ONLY the verified-safe tables to Neon:
- beverage_products (1,118 rows)
- lms2026_payment_matches (22,026 rows)  
- charter_gst_details_2010_2012 (3,805 rows)
- employee_t4_records (59 rows)
- employee_t4_summary (51 rows)
-alcohol_business_tracking (105 rows)

These tables are either:
1. Empty in Neon (beverage_products)
2. Don't exist in Neon (others)

Safe to proceed - verified by analysis.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

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

# Safe tables to sync
SAFE_TABLES = [
    "beverage_products",
    "lms2026_payment_matches",
    "charter_gst_details_2010_2012",
    "employee_t4_records",
    "employee_t4_summary",
    "alcohol_business_tracking",
]

sync_log = {
    "timestamp": datetime.now().isoformat(),
    "tables_synced": [],
    "errors": []
}


def export_table(table):
    """Export table from local database."""
    print(f"\n📤 Exporting {table} from local...")
    
    export_file = Path(f"temp_export_{table}.sql")
    env = os.environ.copy()
    env['PGPASSWORD'] = LOCAL_PASSWORD
    
    try:
        # Export table structure and data
        result = subprocess.run([
            "pg_dump",
            "-h", LOCAL_HOST,
            "-U", LOCAL_USER,
            "-d", LOCAL_DB,
            "--table", f"public.{table}",
            "--no-owner",
            "--no-privileges",
            "-f", str(export_file)
        ], env=env, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            size_kb = export_file.stat().st_size / 1024
            print(f"   ✅ Exported: {export_file} ({size_kb:.1f} KB)")
            return export_file
        else:
            print(f"   ❌ Export failed: {result.stderr}")
            return None
    except Exception as e:
        print(f"   ❌ Export failed: {e}")
        return None


def import_to_neon(table, export_file):
    """Import table to Neon."""
    print(f"\n📥 Importing {table} to Neon...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = NEON_PASSWORD
    
    try:
        # Import using psql
        result = subprocess.run([
            "psql",
            "-h", NEON_HOST,
            "-U", NEON_USER,
            "-d", NEON_DB,
            "-f", str(export_file)
        ], env=env, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 or "ERROR" not in result.stderr:
            print(f"   ✅ Imported successfully")
            return True
        else:
            # Check if it's just warnings
            if result.stderr and "WARNING" in result.stderr and "ERROR" not in result.stderr:
                print(f"   ✅ Imported with warnings: {result.stderr[:200]}")
                return True
            else:
                print(f"   ❌ Import failed: {result.stderr[:500]}")
                return False
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False


def verify_sync(table):
    """Verify table was synced correctly."""
    print(f"\n✓ Verifying {table}...")
    
    try:
        # Get local count
        local_conn = psycopg2.connect(
            host=LOCAL_HOST, database=LOCAL_DB,
            user=LOCAL_USER, password=LOCAL_PASSWORD
        )
        local_cur = local_conn.cursor()
        local_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        local_count = local_cur.fetchone()[0]
        local_cur.close()
        local_conn.close()
        
        # Get Neon count
        neon_conn = psycopg2.connect(
            host=NEON_HOST, database=NEON_DB,
            user=NEON_USER, password=NEON_PASSWORD,
            sslmode='require', connect_timeout=10
        )
        neon_cur = neon_conn.cursor()
        neon_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        neon_count = neon_cur.fetchone()[0]
        neon_cur.close()
        neon_conn.close()
        
        if local_count == neon_count:
            print(f"   ✅ Verified: Local={local_count:,} | Neon={neon_count:,} rows")
            return True
        else:
            print(f"   ⚠️ Count mismatch: Local={local_count:,} | Neon={neon_count:,} rows")
            return False
            
    except Exception as e:
        print(f"   ⚠️ Verification failed: {e}")
        return False


def cleanup_export_files():
    """Clean up temporary export files."""
    print(f"\n🧹 Cleaning up temporary files...")
    for file in Path(".").glob("temp_export_*.sql"):
        file.unlink()
        print(f"   Deleted: {file}")


def main():
    """Sync safe tables to Neon."""
    print("=" * 80)
    print("SAFE TABLE SYNC TO NEON")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"Tables to sync: {len(SAFE_TABLES)}")
    for table in SAFE_TABLES:
        print(f"  - {table}")
    
    print("\n" + "=" * 80)
    input("Press ENTER to proceed with sync (or Ctrl+C to cancel)...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    
    for i, table in enumerate(SAFE_TABLES, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(SAFE_TABLES)}] Syncing: {table}")
        print(f"{'=' * 80}")
        
        # Export from local
        export_file = export_table(table)
        if not export_file:
            failed += 1
            sync_log["errors"].append(f"{table}: Export failed")
            continue
        
        # Import to Neon
        if import_to_neon(table, export_file):
            # Verify
            if verify_sync(table):
                successful += 1
                sync_log["tables_synced"].append(table)
                print(f"\n✅ {table} sync COMPLETE")
            else:
                failed += 1
                sync_log["errors"].append(f"{table}: Verification failed")
                print(f"\n⚠️ {table} sync completed but verification failed")
        else:
            failed += 1
            sync_log["errors"].append(f"{table}: Import failed")
            print(f"\n❌ {table} sync FAILED")
    
    # Cleanup
    cleanup_export_files()
    
    # Summary
    print("\n" + "=" * 80)
    print("SYNC SUMMARY")
    print("=" * 80)
    print(f"\n✅ Successful: {successful}/{len(SAFE_TABLES)}")
    print(f"❌ Failed: {failed}/{len(SAFE_TABLES)}")
    
    if sync_log["tables_synced"]:
        print(f"\nTables synced:")
        for table in sync_log["tables_synced"]:
            print(f"  ✅ {table}")
    
    if sync_log["errors"]:
        print(f"\nErrors:")
        for error in sync_log["errors"]:
            print(f"  ❌ {error}")
    
    # Save log
    import json
    log_file = f"sync_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, 'w') as f:
        json.dump(sync_log, f, indent=2)
    
    print(f"\n💾 Sync log saved to: {log_file}")
    print(f"\n✅ Sync complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if failed == 0:
        print("\n🎉 ALL TABLES SYNCED SUCCESSFULLY!")
    elif failed < len(SAFE_TABLES):
        print("\n⚠️ Some tables failed - review errors above")
    else:
        print("\n❌ All syncs failed - check connection and permissions")


if __name__ == "__main__":
    main()

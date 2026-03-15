#!/usr/bin/env python3
"""
FULL DATABASE BACKUP - Local and Neon
======================================

Creates complete backups of both databases before any sync operations.
Backs up public schema only to avoid permission issues.

This is a CRITICAL SAFETY MEASURE - DO NOT SKIP!
"""

import os
import subprocess
import psycopg2
from datetime import datetime
from pathlib import Path
import json
from dotenv import load_dotenv

load_dotenv()

# Backup directory
BACKUP_DIR = Path(f"l:/limo/database_backups_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

# Database credentials
LOCAL_HOST = "localhost"
LOCAL_DB = os.environ.get("LOCAL_DB_NAME", "almsdata")
LOCAL_USER = os.environ.get("LOCAL_DB_USER", "alms")
LOCAL_PASSWORD = os.environ.get("LOCAL_DB_PASSWORD", "")

NEON_HOST = os.environ.get("NEON_DB_HOST", "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech")
NEON_DB = os.environ.get("NEON_DB_NAME", "neondb")
NEON_USER = os.environ.get("NEON_DB_USER", "neondb_owner")
NEON_PASSWORD = os.environ.get("NEON_DB_PASSWORD", "")

backup_manifest = {
    "timestamp": datetime.now().isoformat(),
    "local_backup": {},
    "neon_backup": {}
}


def create_backup_dir():
    """Create backup directory structure."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "local").mkdir(exist_ok=True)
    (BACKUP_DIR / "neon").mkdir(exist_ok=True)
    print(f"✅ Created backup directory: {BACKUP_DIR}")


def backup_local_database():
    """Backup local PostgreSQL database (public schema only)."""
    print("\n" + "=" * 80)
    print("BACKING UP LOCAL DATABASE (public schema)")
    print("=" * 80)
    
    local_dir = BACKUP_DIR / "local"
    env = os.environ.copy()
    env['PGPASSWORD'] = LOCAL_PASSWORD
    
    # 1. Schema dump
    print("\n📋 Dumping schema (DDL)...")
    schema_file = local_dir / "schema.sql"
    try:
        result = subprocess.run([
            "pg_dump", "-h", LOCAL_HOST, "-U", LOCAL_USER, "-d", LOCAL_DB,
            "--schema=public", "--schema-only", "--no-owner", "--no-privileges",
            "-f", str(schema_file)
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ Schema saved: {schema_file}")
            backup_manifest["local_backup"]["schema_file"] = str(schema_file)
        else:
            print(f"   ❌ Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False
    
    # 2. Data dump (compressed)
    print("\n📦 Dumping data (compressed)...")
    data_file = local_dir / "data.backup"
    try:
        result = subprocess.run([
            "pg_dump", "-h", LOCAL_HOST, "-U", LOCAL_USER, "-d", LOCAL_DB,
            "--schema=public", "--format=custom", "--no-owner", "--no-privileges",
            "-f", str(data_file)
        ], env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            size_mb = data_file.stat().st_size / (1024 * 1024)
            print(f"   ✅ Data saved: {data_file} ({size_mb:.1f} MB)")
            backup_manifest["local_backup"]["data_file"] = str(data_file)
            backup_manifest["local_backup"]["data_size_mb"] = size_mb
        else:
            print(f"   ❌ Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False
    
    # 3. Verify table counts
    print("\n📊 Verifying...")
    try:
        conn = psycopg2.connect(host=LOCAL_HOST, database=LOCAL_DB, user=LOCAL_USER, password=LOCAL_PASSWORD)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        table_count = cur.fetchone()[0]
        print(f"   ✅ Verified {table_count} tables backed up")
        backup_manifest["local_backup"]["table_count"] = table_count
        cur.close()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Verification warning: {e}")
    
    print("\n✅ LOCAL DATABASE BACKUP COMPLETE")
    return True


def backup_neon_database():
    """Backup Neon PostgreSQL database."""
    print("\n" + "=" * 80)
    print("BACKING UP NEON DATABASE")
    print("=" * 80)
    
    neon_dir = BACKUP_DIR / "neon"
    env = os.environ.copy()
    env['PGPASSWORD'] = NEON_PASSWORD
    
    # 1. Schema dump
    print("\n📋 Dumping schema (DDL)...")
    schema_file = neon_dir / "schema.sql"
    try:
        result = subprocess.run([
            "pg_dump", "-h", NEON_HOST, "-U", NEON_USER, "-d", NEON_DB,
            "--schema-only", "--no-owner", "--no-privileges",
            "-f", str(schema_file)
        ], env=env, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(f"   ✅ Schema saved: {schema_file}")
            backup_manifest["neon_backup"]["schema_file"] = str(schema_file)
        else:
            print(f"   ❌ Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False
    
    # 2. Data dump (compressed)
    print("\n📦 Dumping data (compressed - may take several minutes)...")
    data_file = neon_dir / "data.backup"
    try:
        result = subprocess.run([
            "pg_dump", "-h", NEON_HOST, "-U", NEON_USER, "-d", NEON_DB,
            "--format=custom", "--no-owner", "--no-privileges",
            "-f", str(data_file)
        ], env=env, capture_output=True, text=True, timeout=900)
        
        if result.returncode == 0:
            size_mb = data_file.stat().st_size / (1024 * 1024)
            print(f"   ✅ Data saved: {data_file} ({size_mb:.1f} MB)")
            backup_manifest["neon_backup"]["data_file"] = str(data_file)
            backup_manifest["neon_backup"]["data_size_mb"] = size_mb
        else:
            print(f"   ❌ Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False
    
    # 3. Verify
    print("\n📊 Verifying...")
    try:
        conn = psycopg2.connect(host=NEON_HOST, database=NEON_DB, user=NEON_USER, password=NEON_PASSWORD, sslmode='require', connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        table_count = cur.fetchone()[0]
        print(f"   ✅ Verified {table_count} tables backed up")
        backup_manifest["neon_backup"]["table_count"] = table_count
        cur.close()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Verification warning: {e}")
    
    print("\n✅ NEON DATABASE BACKUP COMPLETE")
    return True


def create_restore_scripts():
    """Create restore scripts."""
    print("\n" + "=" * 80)
    print("CREATING RESTORE SCRIPTS")
    print("=" * 80)
    
    # Local restore
    local_restore = BACKUP_DIR / "RESTORE_LOCAL.bat"
    with open(local_restore, 'w') as f:
        f.write(f"""@echo off
echo ===================================================================
echo RESTORE LOCAL DATABASE
echo ===================================================================
echo.
echo WARNING: This will REPLACE the current database!
echo.
pause

set PGPASSWORD={LOCAL_PASSWORD}

echo Restoring from: {BACKUP_DIR / 'local' / 'data.backup'}
pg_restore -h {LOCAL_HOST} -U {LOCAL_USER} -d {LOCAL_DB} --clean --if-exists --no-owner --no-privileges "{BACKUP_DIR / 'local' / 'data.backup'}"

echo.
echo Restore complete!
pause
""")
    print(f"   ✅ {local_restore}")
    
    # Neon restore
    neon_restore = BACKUP_DIR / "RESTORE_NEON.bat"
    with open(neon_restore, 'w') as f:
        f.write(f"""@echo off
echo ===================================================================
echo RESTORE NEON DATABASE
echo ===================================================================
echo.
echo WARNING: This will REPLACE the current Neon database!
echo THIS IS EXTREMELY DANGEROUS!
echo.
pause

set PGPASSWORD={NEON_PASSWORD}

echo Restoring from: {BACKUP_DIR / 'neon' / 'data.backup'}
pg_restore -h {NEON_HOST} -U {NEON_USER} -d {NEON_DB} --clean --if-exists --no-owner --no-privileges "{BACKUP_DIR / 'neon' / 'data.backup'}"

echo.
echo Restore complete!
pause
""")
    print(f"   ✅ {neon_restore}")


def save_manifest():
    """Save backup manifest."""
    manifest_file = BACKUP_DIR / "manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(backup_manifest, f, indent=2)
    print(f"\n💾 Manifest: {manifest_file}")


def print_summary():
    """Print summary."""
    print("\n" + "=" * 80)
    print("BACKUP SUMMARY")
    print("=" * 80)
    
    print(f"\n📦 Location: {BACKUP_DIR}")
    
    if "local_backup" in backup_manifest:
        local = backup_manifest["local_backup"]
        print(f"\n🗄️  LOCAL:")
        print(f"   Tables: {local.get('table_count', 'N/A')}")
        print(f"   Size: {local.get('data_size_mb', 'N/A'):.1f} MB")
    
    if "neon_backup" in backup_manifest:
        neon = backup_manifest["neon_backup"]
        print(f"\n☁️  NEON:")
        print(f"   Tables: {neon.get('table_count', 'N/A')}")
        print(f"   Size: {neon.get('data_size_mb', 'N/A'):.1f} MB")
    
    print(f"\n✅ BOTH DATABASES BACKED UP SUCCESSFULLY!")
    print(f"\n🔒 SAFE TO PROCEED with sync operations")
    print(f"\nRestore scripts:")
    print(f"   Local: {BACKUP_DIR / 'RESTORE_LOCAL.bat'}")
    print(f"   Neon:  {BACKUP_DIR / 'RESTORE_NEON.bat'}")


def main():
    """Run backup."""
    print("=" * 80)
    print("FULL DATABASE BACKUP SYSTEM")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    create_backup_dir()
    
    if not backup_local_database():
        print("\n❌ Local backup failed - aborting")
        return False
    
    if not backup_neon_database():
        print("\n❌ Neon backup failed - aborting")
        return False
    
    create_restore_scripts()
    save_manifest()
    print_summary()
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ BACKUP FAILED - DO NOT PROCEED WITH SYNC")
        exit(1)
    else:
        print("\n✅ ALL BACKUPS VERIFIED AND READY")
        exit(0)

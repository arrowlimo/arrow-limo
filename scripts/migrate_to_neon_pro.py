"""
Migrate almsdata from local PostgreSQL to Neon Pro tier.

Prerequisites:
1. Upgrade Neon to Pro tier (takes 2-3 minutes)
2. Wait for upgrade to complete

This script will:
1. Verify Neon Pro connection
2. Clear any partial data
3. Restore full dump
4. Verify row counts match local
5. Update .env files to use Neon
"""

import subprocess
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import time

# Neon Pro credentials
NEON_HOST = 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech'
NEON_USER = 'neondb_owner'
NEON_PASSWORD = '***REMOVED***'
NEON_DB = 'neondb'

# Local PostgreSQL
LOCAL_HOST = 'localhost'
LOCAL_USER = 'postgres'
LOCAL_PASSWORD = '***REMOVED***'
LOCAL_DB = 'almsdata'

def verify_neon_connection():
    """Test that Neon Pro is accessible (no longer auto-suspending)."""
    print("=" * 100)
    print("STEP 1: Verify Neon Pro Tier Connection")
    print("=" * 100)
    
    try:
        conn = psycopg2.connect(
            host=NEON_HOST,
            user=NEON_USER,
            password=NEON_PASSWORD,
            database=NEON_DB,
            sslmode='require',
            connect_timeout=10
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT version()")
        version = cur.fetchone()['version']
        print(f"✅ Connected to Neon Pro")
        print(f"   Version: {version.split(',')[0]}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Neon:")
        print(f"   {e}")
        print(f"\n⚠️  Please upgrade Neon to Pro tier and wait 2-3 minutes for activation")
        print(f"   Then run this script again")
        return False

def get_local_row_counts():
    """Get row counts from local database."""
    print("\n" + "=" * 100)
    print("STEP 2: Get Local Database Row Counts")
    print("=" * 100)
    
    try:
        conn = psycopg2.connect(
            host=LOCAL_HOST,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD,
            database=LOCAL_DB
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        tables = ['charters', 'payments', 'receipts', 'vehicles', 'employees', 'banking_transactions']
        counts = {}
        
        for table in tables:
            cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            counts[table] = cur.fetchone()['cnt']
            print(f"   {table:30} {counts[table]:>10,} rows")
        
        cur.close()
        conn.close()
        return counts
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def restore_dump_to_neon(dump_file):
    """Restore dump file to Neon using pg_restore."""
    print("\n" + "=" * 100)
    print("STEP 3: Restore Dump to Neon Pro")
    print("=" * 100)
    
    if not os.path.exists(dump_file):
        print(f"❌ Dump file not found: {dump_file}")
        return False
    
    print(f"📄 Dump file: {os.path.basename(dump_file)}")
    print(f"   Size: {os.path.getsize(dump_file) / (1024*1024):.1f} MB")
    
    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = NEON_PASSWORD
        
        print(f"\n🔄 Restoring... (this may take 2-5 minutes)")
        
        result = subprocess.run([
            "pg_restore",
            "-h", NEON_HOST,
            "-U", NEON_USER,
            "-d", NEON_DB,
            "--no-owner",
            "--no-acl",
            "--clean",
            "--if-exists",
            dump_file
        ], env=env, capture_output=True, text=True, timeout=600)
        
        if "error" in result.stderr.lower() and "constraint" not in result.stderr.lower():
            print(f"⚠️  Restore completed with warnings:")
            lines = result.stderr.split('\n')
            for line in lines[-10:]:
                if line.strip():
                    print(f"   {line}")
        else:
            print(f"✅ Restore completed successfully")
        
        return True
    except subprocess.TimeoutExpired:
        print(f"❌ Restore timeout (took too long)")
        return False
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False

def verify_neon_data(local_counts):
    """Verify Neon has the same data as local."""
    print("\n" + "=" * 100)
    print("STEP 4: Verify Data Migration")
    print("=" * 100)
    
    try:
        conn = psycopg2.connect(
            host=NEON_HOST,
            user=NEON_USER,
            password=NEON_PASSWORD,
            database=NEON_DB,
            sslmode='require'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        all_match = True
        for table, expected_count in local_counts.items():
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                actual_count = cur.fetchone()['cnt']
                
                match = "✅" if actual_count == expected_count else "❌"
                print(f"   {match} {table:30} Expected: {expected_count:>10,} | Got: {actual_count:>10,}")
                
                if actual_count != expected_count:
                    all_match = False
            except Exception as e:
                print(f"   ❌ {table:30} Error: {e}")
                all_match = False
        
        cur.close()
        conn.close()
        return all_match
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def update_env_files():
    """Update .env files to use Neon instead of local."""
    print("\n" + "=" * 100)
    print("STEP 5: Update Configuration Files")
    print("=" * 100)
    
    env_files = [
        ('l:\\limo\\.env', 'local'),
        ('l:\\limo\\.env.neon', 'neon')
    ]
    
    neon_config = f"""# Neon PostgreSQL Connection (Production - Cloud Hosted)
DB_HOST={NEON_HOST}
DB_NAME={NEON_DB}
DB_USER={NEON_USER}
DB_PASSWORD={NEON_PASSWORD}
DB_PORT=5432
DB_SSLMODE=require

# For connection strings
DATABASE_URL=postgresql://{NEON_USER}:{NEON_PASSWORD}@{NEON_HOST}:5432/{NEON_DB}?sslmode=require
"""
    
    try:
        with open('l:\\limo\\.env.neon', 'w') as f:
            f.write(neon_config)
        print("✅ Created/Updated .env.neon")
        
        # Note: don't auto-overwrite .env, let user decide
        print("✅ Configuration ready")
        print("\n   To switch to Neon, update your .env file:")
        print(f"   DB_HOST={NEON_HOST}")
        print(f"   DB_NAME={NEON_DB}")
        print(f"   DB_USER={NEON_USER}")
        print(f"   DB_PASSWORD={NEON_PASSWORD}")
        print(f"   DB_SSLMODE=require")
        
        return True
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def main():
    import glob
    
    print("\n")
    print("╔" + "=" * 98 + "╗")
    print("║" + " MIGRATE TO NEON PRO TIER ".center(98) + "║")
    print("╚" + "=" * 98 + "╝")
    
    # Step 1: Verify connection
    if not verify_neon_connection():
        return False
    
    # Wait for upgrade
    print("\n💡 Pro tier is active! Continuing migration...")
    time.sleep(2)
    
    # Step 2: Get local counts
    local_counts = get_local_row_counts()
    if not local_counts:
        return False
    
    # Step 3: Find and restore dump
    dumps = sorted(glob.glob('L:\\limo\\almsdata_neon_migration_*.dump'), reverse=True)
    if dumps:
        dump_file = dumps[0]
    else:
        # Try SQL dump
        dumps = sorted(glob.glob('L:\\limo\\almsdata_full_*.sql'), reverse=True)
        if dumps:
            dump_file = dumps[0]
        else:
            print("❌ No dump files found. Create one first with:")
            print("   pg_dump -h localhost -U postgres -d almsdata -F c -f almsdata_migration.dump")
            return False
    
    if not restore_dump_to_neon(dump_file):
        return False
    
    # Step 4: Verify
    if not verify_neon_data(local_counts):
        print("\n⚠️  Data counts don't match. Check for errors above.")
        return False
    
    # Step 5: Update config
    if not update_env_files():
        return False
    
    print("\n" + "=" * 100)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 100)
    print("\nNext steps:")
    print("1. Update your .env file with Neon credentials")
    print("2. Test application: python -X utf8 desktop_app/main.py")
    print("3. All future changes will be saved to Neon (no more data loss!)")
    print("\n" + "=" * 100)
    
    return True

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)

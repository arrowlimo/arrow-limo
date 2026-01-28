"""
Test Neon database connection and setup
"""
import psycopg2
import os
from datetime import datetime

print("\n" + "="*80)
print("NEON DATABASE CONNECTION TEST")
print("="*80 + "\n")

# Neon connection details (you'll need to provide these)
NEON_HOST = input("Enter Neon hostname (e.g., ep-xxx-xxx.us-east-2.aws.neon.tech): ").strip()
NEON_DB = input("Enter database name [almsdata]: ").strip() or "almsdata"
NEON_USER = input("Enter username [neondb_owner]: ").strip() or "neondb_owner"
NEON_PASSWORD = input("Enter password: ").strip()

if not NEON_HOST or not NEON_PASSWORD:
    print("\n❌ Hostname and password are required!")
    exit(1)

print("\n" + "-"*80)
print("Testing connection...")
print("-"*80 + "\n")

try:
    # Test connection
    conn = psycopg2.connect(
        host=NEON_HOST,
        port=5432,
        database=NEON_DB,
        user=NEON_USER,
        password=NEON_PASSWORD,
        sslmode='require'  # Neon requires SSL
    )
    
    cur = conn.cursor()
    
    # Test 1: Basic connection
    cur.execute("SELECT version()")
    version = cur.fetchone()[0]
    print(f"✅ Connected successfully!")
    print(f"   PostgreSQL version: {version[:50]}...")
    
    # Test 2: Database size
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    size = cur.fetchone()[0]
    print(f"✅ Database size: {size}")
    
    # Test 3: Check if tables exist
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    table_count = cur.fetchone()[0]
    print(f"✅ Tables found: {table_count}")
    
    if table_count > 0:
        # Test 4: Sample data
        cur.execute("""
            SELECT table_name, 
                   pg_size_pretty(pg_total_relation_size('public.'||table_name)) as size
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY pg_total_relation_size('public.'||table_name) DESC
            LIMIT 5
        """)
        print(f"\n📊 Top 5 tables:")
        for table, tbl_size in cur.fetchall():
            print(f"   - {table}: {tbl_size}")
        
        # Test 5: Check for users table (authentication)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'users'
            )
        """)
        has_users = cur.fetchone()[0]
        if has_users:
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            print(f"\n✅ Users table exists with {user_count} users")
        else:
            print(f"\n⚠️  Users table not found (will need to import data)")
    else:
        print(f"\n⚠️  No tables found - database is empty (need to import)")
    
    # Test 6: Write test
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS connection_test (
                test_id SERIAL PRIMARY KEY,
                test_time TIMESTAMP DEFAULT NOW(),
                test_message TEXT
            )
        """)
        cur.execute("""
            INSERT INTO connection_test (test_message) 
            VALUES (%s)
            RETURNING test_id, test_time
        """, (f"Connection test from local machine at {datetime.now()}",))
        test_id, test_time = cur.fetchone()
        conn.commit()
        print(f"\n✅ Write test successful (ID: {test_id}, Time: {test_time})")
        
        # Cleanup
        cur.execute("DROP TABLE connection_test")
        conn.commit()
        print(f"✅ Cleanup successful")
    except Exception as e:
        conn.rollback()
        print(f"\n⚠️  Write test failed: {e}")
        print(f"   (This is OK if database is read-only)")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)
    print("CONNECTION TEST: SUCCESS ✅")
    print("="*80)
    print(f"\nConnection details:")
    print(f"  Host: {NEON_HOST}")
    print(f"  Database: {NEON_DB}")
    print(f"  User: {NEON_USER}")
    print(f"  SSL: Required")
    
    # Save to .env file option
    print(f"\n" + "-"*80)
    save = input("Save these credentials to .env file? (y/n): ").strip().lower()
    if save == 'y':
        env_content = f"""# Neon Database Connection
NEON_HOST={NEON_HOST}
NEON_DB={NEON_DB}
NEON_USER={NEON_USER}
NEON_PASSWORD={NEON_PASSWORD}
NEON_SSL=require

# Use Neon instead of local (set to 'true' to enable)
USE_NEON=false
"""
        with open('.env.neon', 'w') as f:
            f.write(env_content)
        print(f"✅ Saved to .env.neon")
        print(f"   To use Neon, set USE_NEON=true in your .env file")
    
except psycopg2.OperationalError as e:
    print(f"\n❌ Connection failed!")
    print(f"   Error: {e}")
    print(f"\n   Common issues:")
    print(f"   - Wrong hostname/credentials")
    print(f"   - Neon project is suspended (inactive for 7 days)")
    print(f"   - Network/firewall blocking connection")
    print(f"   - SSL certificate issues")
    print(f"\n   To reactivate a suspended Neon project:")
    print(f"   1. Go to https://console.neon.tech")
    print(f"   2. Select your project")
    print(f"   3. Click 'Resume' if suspended")
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

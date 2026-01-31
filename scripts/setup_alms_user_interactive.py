#!/usr/bin/env python3
"""
Setup ALMS user - Interactive version
Prompts for postgres superuser password and creates ALMS user
"""

import psycopg2
import getpass
import sys

def setup_alms_user():
    """Create ALMS user with proper permissions"""
    
    print("\n" + "="*70)
    print("🔐 ARROW LIMOUSINE - ALMS PostgreSQL User Setup")
    print("="*70 + "\n")
    
    # Get postgres password
    postgres_password = getpass.getpass("Enter PostgreSQL 'postgres' user password: ")
    
    try:
        print("\n🔗 Connecting to PostgreSQL as postgres user...")
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='almsdata',
            user='postgres',
            password=postgres_password
        )
        print("✅ Connected successfully!\n")
        
        cur = conn.cursor()
        
        # Check if ALMS user exists
        print("1️⃣  Checking if ALMS user exists...")
        cur.execute("SELECT usename FROM pg_user WHERE usename='alms';")
        result = cur.fetchone()
        
        if result:
            print("   ℹ️  ALMS user already exists")
        else:
            print("   Creating ALMS user...")
            cur.execute("CREATE USER alms WITH PASSWORD 'alms_secure_password_2024';")
            print("   ✅ ALMS user created")
        
        # Grant permissions
        print("\n2️⃣  Setting database permissions...")
        
        cur.execute("GRANT CONNECT ON DATABASE almsdata TO alms;")
        cur.execute("GRANT USAGE ON SCHEMA public TO alms;")
        cur.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO alms;")
        cur.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO alms;")
        
        print("   ✅ Database access granted")
        
        # Set default privileges
        print("\n3️⃣  Setting default privileges for future tables...")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO alms;")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO alms;")
        print("   ✅ Default privileges set")
        
        conn.commit()
        
        # Verify
        print("\n4️⃣  Verifying ALMS user...")
        cur.execute("SELECT usename, usecanlogin FROM pg_user WHERE usename='alms';")
        user_info = cur.fetchone()
        
        if user_info:
            print(f"   ✅ User verified: {user_info[0]} (can login: {user_info[1]})")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*70)
        print("✅ ALMS USER SETUP COMPLETE!")
        print("="*70)
        print("\n📝 Configuration:")
        print("   Username: alms")
        print("   Password: alms_secure_password_2024")
        print("   Database: almsdata")
        print("   Host: localhost")
        print("   Port: 5432")
        print("\n💡 These values are already in .env:")
        print("   LOCAL_DB_USER=alms")
        print("   LOCAL_DB_PASSWORD=alms_secure_password_2024")
        print("\n✨ Desktop app will now use ALMS credentials automatically!")
        
        # Test ALMS connection
        print("\n" + "-"*70)
        print("🧪 Testing ALMS user connection...\n")
        
        try:
            alms_conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='almsdata',
                user='alms',
                password='alms_secure_password_2024'
            )
            print("✅ ALMS user can connect successfully!")
            
            alms_cur = alms_conn.cursor()
            alms_cur.execute("SELECT version();")
            version = alms_cur.fetchone()[0]
            print(f"   PostgreSQL: {version}\n")
            
            alms_cur.close()
            alms_conn.close()
            
        except psycopg2.Error as e:
            print(f"⚠️  ALMS connection test failed: {e}")
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  - Verify PostgreSQL is running")
        print("  - Check postgres password is correct")
        print("  - Verify 'almsdata' database exists")
        print("  - Port 5432 is not blocked by firewall")
        return False
        
    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        print(f"   Code: {e.pgcode}")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == '__main__':
    try:
        success = setup_alms_user()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(1)

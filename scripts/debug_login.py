"""
Debug login issues - test database connection and credentials
"""

import os
import sys
import psycopg2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_app.login_manager import LoginManager, AuthenticationError, AccountLockedError

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

print("=" * 60)
print("LOGIN DEBUG - Testing Connection & Authentication")
print("=" * 60)

# Test 1: Database connection
print("\n[1] Testing Database Connection...")
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    print(f"    ✓ Connected to {DB_HOST}:{DB_NAME}")
    print(f"    ✓ Users in database: {user_count}")
    
    # List all users
    cur.execute("SELECT user_id, username, status FROM users ORDER BY user_id")
    users = cur.fetchall()
    print(f"\n    Available users:")
    for uid, uname, status in users:
        print(f"      - {uname} (ID: {uid}, Status: {status})")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"    ✗ Database connection failed: {e}")
    sys.exit(1)

# Test 2: LoginManager authentication
print("\n[2] Testing LoginManager.authenticate()...")
try:
    login_mgr = LoginManager()
    
    # Test admin user
    print("\n    Testing: admin / TestPassword123!")
    try:
        auth_user = login_mgr.authenticate('admin', 'TestPassword123!', '127.0.0.1')
        print(f"    ✓ Authentication successful!")
        print(f"      - User ID: {auth_user['user_id']}")
        print(f"      - Username: {auth_user['username']}")
        print(f"      - Role: {auth_user['role']}")
    except AccountLockedError as e:
        print(f"    ✗ Account locked: {e}")
    except AuthenticationError as e:
        print(f"    ✗ Authentication failed: {e}")
    
    # Test demo user
    print("\n    Testing: demo / DemoPassword123!")
    try:
        auth_user = login_mgr.authenticate('demo', 'DemoPassword123!', '127.0.0.1')
        print(f"    ✓ Authentication successful!")
        print(f"      - User ID: {auth_user['user_id']}")
        print(f"      - Username: {auth_user['username']}")
        print(f"      - Role: {auth_user['role']}")
    except AccountLockedError as e:
        print(f"    ✗ Account locked: {e}")
    except AuthenticationError as e:
        print(f"    ✗ Authentication failed: {e}")
        
except Exception as e:
    print(f"    ✗ LoginManager error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Debug complete. Check results above.")
print("=" * 60)

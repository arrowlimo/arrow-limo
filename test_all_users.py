import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

import psycopg2

# Connect and check for any users with non-test passwords
conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*70)
print("TESTING REAL USERS")
print("="*70)

# Get all users
cur.execute("""
    SELECT user_id, username, email, role, status, password_hash
    FROM users
    ORDER BY created_at
""")

users = cur.fetchall()
print(f"\nTotal users in database: {len(users)}\n")

from login_manager import LoginManager, AuthenticationError

login_mgr = LoginManager()

# Test each user with their standard password pattern
test_users = [
    ('admin', 'admin123'),
    ('test', 'test123'),
    ('manager', 'manager123'),
    ('dispatcher', 'dispatcher123'),
    ('disp', 'disp123'),
]

print("Testing Standard Passwords:")
print("-" * 70)

for username, password in test_users:
    try:
        result = login_mgr.authenticate(username, password)
        print(f"✅ {username:15} / {password:15} → SUCCESS (role: {result['role']})")
    except AuthenticationError:
        print(f"❌ {username:15} / {password:15} → FAILED")
    except Exception as e:
        print(f"⚠️  {username:15} / {password:15} → ERROR: {e}")

cur.close()
conn.close()

print("\n" + "="*70)
print("TESTING STATUS")
print("="*70)

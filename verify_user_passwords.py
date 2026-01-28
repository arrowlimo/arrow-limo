import psycopg2
import bcrypt

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("USER PASSWORD VERIFICATION")
print("="*80)

# Get all users
cur.execute("SELECT user_id, username, email, password_hash, role, status FROM users ORDER BY user_id")
users = cur.fetchall()

print(f"\nTotal users: {len(users)}\n")

# Test passwords
test_passwords = {
    'admin': 'admin123',
    'manager': 'manager123',
    'dispatcher': 'dispatcher123',
    'paulr': 'balamo2026',
    'david': 'richard2026',
    'matt': 'dispatcher1',
    'mike_richard': 'chauffeur',
    'accountant': '2025ArrowLimo',
    'test': 'test123',
    'disp': 'disp123'
}

print("Testing password authentication:")
print("-" * 80)

for user_id, username, email, password_hash, role, status in users:
    if username in test_passwords:
        expected_password = test_passwords[username]
        
        # Test bcrypt verification
        try:
            if password_hash:
                # Check if hash is valid bcrypt format
                if password_hash.startswith('$2b$') or password_hash.startswith('$2a$'):
                    result = bcrypt.checkpw(expected_password.encode('utf-8'), password_hash.encode('utf-8'))
                    status_icon = "✅" if result else "❌"
                    print(f"{status_icon} {username:15} | Password: {expected_password:15} | Hash valid: {result}")
                else:
                    print(f"❌ {username:15} | INVALID HASH FORMAT: {password_hash[:20]}...")
            else:
                print(f"❌ {username:15} | NO PASSWORD HASH SET")
        except Exception as e:
            print(f"❌ {username:15} | ERROR: {e}")
    else:
        print(f"⚠️  {username:15} | No test password defined")

print("\n" + "="*80)
print("DETAILED USER DATA")
print("="*80)

for user_id, username, email, password_hash, role, status in users:
    print(f"\nUser ID: {user_id}")
    print(f"  Username: {username}")
    print(f"  Email: {email}")
    print(f"  Role: {role}")
    print(f"  Status: {status}")
    print(f"  Password hash: {password_hash[:60] if password_hash else 'NULL'}...")
    
    if username in test_passwords:
        expected = test_passwords[username]
        print(f"  Expected password: {expected}")

cur.close()
conn.close()

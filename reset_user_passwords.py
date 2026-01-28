import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

import psycopg2
import bcrypt

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Test user credentials
users_to_update = [
    ('admin', 'admin123'),
    ('test', 'test123'),
    ('manager', 'manager123'),
    ('dispatcher', 'dispatcher123'),
]

print("Resetting password hashes for test users:")
for username, password in users_to_update:
    # Hash the password
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    # Update database
    cur.execute('''
        UPDATE users 
        SET password_hash = %s, updated_at = NOW()
        WHERE username = %s
    ''', (pwd_hash, username))
    
    print(f"  ✅ {username}: Reset password to '{password}'")

conn.commit()
print("\n✅ All passwords reset successfully!")

cur.close()
conn.close()

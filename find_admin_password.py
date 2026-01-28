import psycopg2
import bcrypt
import os

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

# Get admin user's current hash
cur.execute("SELECT password_hash FROM users WHERE username='admin'")
stored_hash = cur.fetchone()[0]
print(f"Current hash: {stored_hash[:30]}...")

# Test common passwords
test_passwords = [
    "admin",
    "password", 
    "12345",
    "Arrow",
    "***REMOVED***",
    "admin123",
    "administrator",
    ""
]

print("\nTesting passwords:")
for pwd in test_passwords:
    try:
        result = bcrypt.checkpw(pwd.encode('utf-8'), stored_hash.encode('utf-8'))
        print(f"  '{pwd}': {result}")
        if result:
            print(f"\n✓ MATCH FOUND: '{pwd}'")
            break
    except Exception as e:
        print(f"  '{pwd}': ERROR - {e}")

# Generate fresh hash for 'admin'
print("\n--- Generating fresh hash for 'admin' ---")
new_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
print(f"New hash: {new_hash}")
verify = bcrypt.checkpw("admin".encode('utf-8'), new_hash.encode('utf-8'))
print(f"Verification: {verify}")

# Update database
cur.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
conn.commit()
print(f"\n✓ Updated admin password to 'admin'")

cur.close()
conn.close()

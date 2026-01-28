import psycopg2
import bcrypt

# Create the missing users: david, mike, matt
conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

users_to_create = [
    ('david', 'david@arrowlimo.com', 'david2026', 'dispatcher'),
    ('mike', 'mike@arrowlimo.com', 'mike2026', 'dispatcher'),
    ('matt', 'matt@arrowlimo.com', 'matt2026', 'dispatcher'),
]

print("Creating missing users with 2026 passwords:")
print("="*70)

for username, email, password, role in users_to_create:
    # Hash the password
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    # Check if user already exists
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    existing = cur.fetchone()
    
    if existing:
        print(f"⚠️  {username} already exists (ID: {existing[0]})")
    else:
        # Create the user
        cur.execute("""
            INSERT INTO users (username, email, password_hash, role, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING user_id
        """, (username, email, pwd_hash, role))
        
        user_id = cur.fetchone()[0]
        print(f"✅ {username:10} | {email:25} | {password:12} | {role:12} | ID: {user_id}")

conn.commit()
print("\n✅ All users created successfully!")

# Verify
print("\n" + "="*70)
print("Verifying all users:")
print("="*70)

cur.execute("SELECT user_id, username, email, role FROM users ORDER BY user_id")
for row in cur.fetchall():
    print(f"  {row[0]:3} | {row[1]:15} | {row[2]:30} | {row[3]}")

cur.close()
conn.close()

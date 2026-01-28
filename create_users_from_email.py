import psycopg2
import bcrypt

# Create users based on the email screenshot shown
# paulr = balamo2026
# david = richard2026  
# matt = dispatcher1 (unchanged)
# mike_richard = chauffeur (unchanged)
# accountant = 2025ArrowLimo (unchanged)

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

users_to_create = [
    ('david', 'richard@arrowlimo.com', 'richard2026', 'dispatcher'),
    ('matt', 'matt@arrowlimo.com', 'dispatcher1', 'dispatcher'),
    ('mike_richard', 'mike@arrowlimo.com', 'chauffeur', 'driver'),
    ('accountant', 'accountant@arrowlimo.com', '2025ArrowLimo', 'accountant'),
]

# Also update paulr password to balamo2026
print("Updating/creating users from email credentials:")
print("="*80)

# Update paulr's password
pwd_hash = bcrypt.hashpw('balamo2026'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
cur.execute("""
    UPDATE users 
    SET password_hash = %s, updated_at = NOW()
    WHERE username = 'paulr'
""", (pwd_hash,))
print(f"✅ Updated paulr password to: balamo2026")

# Create/update other users
for username, email, password, role in users_to_create:
    # Hash the password
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    # Check if user already exists
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    existing = cur.fetchone()
    
    if existing:
        # Update existing user
        cur.execute("""
            UPDATE users 
            SET password_hash = %s, email = %s, role = %s, updated_at = NOW()
            WHERE username = %s
        """, (pwd_hash, email, role, username))
        print(f"✅ Updated {username:15} | {email:30} | {password:20} | {role}")
    else:
        # Create new user
        cur.execute("""
            INSERT INTO users (username, email, password_hash, role, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING user_id
        """, (username, email, pwd_hash, role))
        
        user_id = cur.fetchone()[0]
        print(f"✅ Created {username:15} | {email:30} | {password:20} | {role} | ID: {user_id}")

conn.commit()

# Now check for permissions/access rights
print("\n" + "="*80)
print("Checking for access rights/permissions:")
print("="*80)

cur.execute("""
    SELECT user_id, username, role, permissions, status
    FROM users
    ORDER BY user_id
""")

for row in cur.fetchall():
    perms = row[3] if row[3] else 'null'
    print(f"  {row[0]:3} | {row[1]:15} | {row[2]:12} | {row[4]:10} | Permissions: {perms}")

cur.close()
conn.close()

print("\n✅ All users created/updated successfully!")
print("\nCredentials from email:")
print("  paulr         / balamo2026")
print("  david         / richard2026")
print("  matt          / dispatcher1")
print("  mike_richard  / chauffeur")
print("  accountant    / 2025ArrowLimo")

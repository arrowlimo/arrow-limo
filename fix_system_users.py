import psycopg2
import json
import bcrypt

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("CHECKING USER TABLE STRUCTURE")
print("="*80)

# Check if system_users table exists and what's in it
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND table_name LIKE '%user%'
    ORDER BY table_name
""")

user_tables = cur.fetchall()
print("\nUser-related tables:")
for table in user_tables:
    print(f"  - {table[0]}")
    
    # Count rows
    cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cur.fetchone()[0]
    print(f"     Rows: {count}")

# Check system_users content
print("\n" + "="*80)
print("SYSTEM_USERS TABLE CONTENT")
print("="*80)

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'system_users'
    ORDER BY ordinal_position
""")

print("\nColumns in system_users:")
for col in cur.fetchall():
    print(f"  {col[0]} ({col[1]})")

cur.execute("SELECT * FROM system_users LIMIT 10")
rows = cur.fetchall()

if rows:
    print(f"\nFirst {len(rows)} rows:")
    for row in rows:
        print(f"  {row}")
else:
    print("\nTable is empty")

# We need to add users to system_users, not just users table
print("\n" + "="*80)
print("ADDING USERS TO SYSTEM_USERS TABLE")
print("="*80)

users_to_add = [
    ('paulr', 'paul@arrowlimo.com', 'balamo2026', 1, 11),  # super_user role + admin role
    ('david', 'richard@arrowlimo.com', 'richard2026', 1, 12),  # dispatch role
    ('matt', 'matt@arrowlimo.com', 'dispatcher1', 1, 12),  # dispatch role
    ('mike_richard', 'mike@arrowlimo.com', 'chauffeur', 1, 10),  # driver role
    ('accountant', 'accountant@arrowlimo.com', '2025ArrowLimo', 1, 3),  # accountant role
]

for username, email, password, active, role_id in users_to_add:
    # Hash password
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    # Check if user exists in system_users
    cur.execute("SELECT user_id FROM system_users WHERE username = %s", (username,))
    existing = cur.fetchone()
    
    if existing:
        # Update
        cur.execute("""
            UPDATE system_users
            SET email = %s, password_hash = %s, active = %s
            WHERE username = %s
        """, (email, pwd_hash, active, username))
        user_id = existing[0]
        print(f"✅ Updated {username:15} in system_users (ID: {user_id})")
    else:
        # Insert
        cur.execute("""
            INSERT INTO system_users (username, email, password_hash, active, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING user_id
        """, (username, email, pwd_hash, active))
        user_id = cur.fetchone()[0]
        print(f"✅ Created {username:15} in system_users (ID: {user_id})")
    
    # Assign role in user_roles
    cur.execute("""
        SELECT id FROM user_roles 
        WHERE user_id = %s AND role_id = %s
    """, (user_id, role_id))
    
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO user_roles (user_id, role_id, assigned_at)
            VALUES (%s, %s, NOW())
        """, (user_id, role_id))
        print(f"   → Assigned role_id {role_id}")

conn.commit()

# Verify
print("\n" + "="*80)
print("FINAL VERIFICATION")
print("="*80)

cur.execute("""
    SELECT 
        su.user_id,
        su.username,
        su.email,
        su.active,
        sr.role_name
    FROM system_users su
    LEFT JOIN user_roles ur ON su.user_id = ur.user_id
    LEFT JOIN system_roles sr ON ur.role_id = sr.role_id
    ORDER BY su.user_id
""")

for row in cur.fetchall():
    print(f"{row[0]:3} | {row[1]:15} | {row[2]:30} | Active: {row[3]} | Role: {row[4] if row[4] else 'None'}")

cur.close()
conn.close()

print("\n✅ All users configured in system_users with proper role assignments!")

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
print("UPDATING PASSWORDS IN SYSTEM_USERS")
print("="*80)

# Update passwords for existing users in system_users
password_updates = {
    'paulr': 'balamo2026',
    'david': 'richard2026',
    'matt': 'dispatcher1',
    'mikerichards': 'chauffeur',  # Note: username is mikerichards, not mike_richard
}

for username, password in password_updates.items():
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    cur.execute("""
        UPDATE system_users
        SET password_hash = %s, 
            password_changed_at = NOW(),
            updated_at = NOW()
        WHERE username = %s
        RETURNING user_id
    """, (pwd_hash, username))
    
    result = cur.fetchone()
    if result:
        print(f"✅ Updated {username:15} → {password}")
    else:
        print(f"⚠️  User {username} not found in system_users")

# Add accountant if missing
cur.execute("SELECT user_id FROM system_users WHERE username = 'accountant'")
if not cur.fetchone():
    pwd_hash = bcrypt.hashpw('2025ArrowLimo'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    cur.execute("""
        INSERT INTO system_users (username, email, full_name, password_hash, is_active, created_at, updated_at, password_changed_at)
        VALUES ('accountant', 'accountant@arrowlimo.com', 'Accountant', %s, true, NOW(), NOW(), NOW())
        RETURNING user_id
    """, (pwd_hash,))
    user_id = cur.fetchone()[0]
    print(f"✅ Created accountant (ID: {user_id}) → 2025ArrowLimo")
else:
    pwd_hash = bcrypt.hashpw('2025ArrowLimo'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    cur.execute("""
        UPDATE system_users
        SET password_hash = %s, password_changed_at = NOW(), updated_at = NOW()
        WHERE username = 'accountant'
    """, (pwd_hash,))
    print(f"✅ Updated accountant → 2025ArrowLimo")

conn.commit()

# Verify final state
print("\n" + "="*80)
print("FINAL SYSTEM_USERS STATE")
print("="*80)

cur.execute("""
    SELECT 
        su.user_id,
        su.username,
        su.email,
        su.full_name,
        su.is_active,
        sr.role_name
    FROM system_users su
    LEFT JOIN user_roles ur ON su.user_id = ur.user_id
    LEFT JOIN system_roles sr ON ur.role_id = sr.role_id
    ORDER BY su.user_id
""")

print("\n{:3} | {:15} | {:30} | {:15} | {:6} | Role".format("ID", "Username", "Email", "Full Name", "Active"))
print("-" * 100)
for row in cur.fetchall():
    print(f"{row[0]:3} | {row[1]:15} | {row[2]:30} | {row[3] if row[3] else '':15} | {str(row[4]):6} | {row[5] if row[5] else 'None'}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ ALL USERS UPDATED WITH CORRECT PASSWORDS")
print("="*80)
print("\nLogin Credentials (from email screenshot):")
print("  paulr          / balamo2026")
print("  david          / richard2026")
print("  matt           / dispatcher1")
print("  mikerichards   / chauffeur")
print("  accountant     / 2025ArrowLimo")

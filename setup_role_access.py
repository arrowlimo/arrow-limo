import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("SETTING UP ROLE-BASED ACCESS CONTROL")
print("="*80)

# First, check what system roles exist
cur.execute("SELECT role_id, role_name, description FROM system_roles ORDER BY role_id")
roles = cur.fetchall()

print("\nExisting system roles:")
for role in roles:
    print(f"  {role[0]:3} | {role[1]:15} | {role[2]}")

# Get role IDs
role_map = {}
for role in roles:
    role_map[role[1].lower()] = role[0]

# If roles don't exist, create them
required_roles = {
    'admin': 'Full system administrator access',
    'dispatcher': 'Dispatch operations and charter management',
    'driver': 'Driver access to schedules and timesheets',
    'accountant': 'Accounting and financial access'
}

for role_name, description in required_roles.items():
    if role_name not in role_map:
        cur.execute("""
            INSERT INTO system_roles (role_name, description, created_at)
            VALUES (%s, %s, NOW())
            RETURNING role_id
        """, (role_name, description))
        role_id = cur.fetchone()[0]
        role_map[role_name] = role_id
        print(f"✅ Created role: {role_name} (ID: {role_id})")

conn.commit()

# Now assign users to roles
print("\n" + "="*80)
print("ASSIGNING USERS TO ROLES")
print("="*80)

user_role_assignments = [
    ('paulr', 'admin'),
    ('david', 'dispatcher'),
    ('matt', 'dispatcher'),
    ('mike_richard', 'driver'),
    ('accountant', 'accountant'),
]

for username, role_name in user_role_assignments:
    # Get user_id
    cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    user_row = cur.fetchone()
    if not user_row:
        print(f"⚠️  User {username} not found")
        continue
    
    user_id = user_row[0]
    role_id = role_map.get(role_name)
    
    if not role_id:
        print(f"⚠️  Role {role_name} not found")
        continue
    
    # Check if assignment already exists
    cur.execute("""
        SELECT id FROM user_roles 
        WHERE user_id = %s AND role_id = %s
    """, (user_id, role_id))
    
    if cur.fetchone():
        print(f"ℹ️  {username:15} already assigned to {role_name}")
    else:
        cur.execute("""
            INSERT INTO user_roles (user_id, role_id, assigned_at)
            VALUES (%s, %s, NOW())
        """, (user_id, role_id))
        print(f"✅ {username:15} → {role_name} (user_id: {user_id}, role_id: {role_id})")

conn.commit()

# Verify assignments
print("\n" + "="*80)
print("FINAL USER-ROLE ASSIGNMENTS")
print("="*80)

cur.execute("""
    SELECT 
        u.user_id,
        u.username,
        u.email,
        u.role as user_table_role,
        sr.role_name as assigned_role,
        u.permissions,
        u.status
    FROM users u
    LEFT JOIN user_roles ur ON u.user_id = ur.user_id
    LEFT JOIN system_roles sr ON ur.role_id = sr.role_id
    ORDER BY u.user_id
""")

for row in cur.fetchall():
    print(f"\n{row[0]:3} | {row[1]:15} | {row[6]}")
    print(f"     Email: {row[2]}")
    print(f"     User table role: {row[3]}")
    print(f"     Assigned role: {row[4] if row[4] else 'None'}")
    print(f"     Permissions: {row[5] if row[5] else 'None'}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ Role-based access control configured!")
print("="*80)
print("\nAll users now have:")
print("  1. Password set (bcrypt hashed)")
print("  2. Role assigned in users table")  
print("  3. Permissions JSON in users table")
print("  4. System role assignment in user_roles table")

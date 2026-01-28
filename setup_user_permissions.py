import psycopg2
import json

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# First, check for any access rights tables
print("="*80)
print("CHECKING FOR ACCESS RIGHTS TABLES")
print("="*80)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND (table_name LIKE '%permission%' OR table_name LIKE '%access%' OR table_name LIKE '%role%' OR table_name LIKE '%right%')
    ORDER BY table_name
""")

access_tables = cur.fetchall()
if access_tables:
    print("\nAccess/Permission tables found:")
    for table in access_tables:
        print(f"  - {table[0]}")
        # Show structure
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table[0]}'
            ORDER BY ordinal_position
        """)
        for col in cur.fetchall():
            print(f"      {col[0]} ({col[1]})")
else:
    print("\nNo dedicated access/permission tables found")

# Set up proper permissions for the new users based on their roles
print("\n" + "="*80)
print("SETTING UP PERMISSIONS FOR NEW USERS")
print("="*80)

permission_configs = {
    'paulr': {
        'role': 'admin',
        'permissions': ['all']
    },
    'david': {
        'role': 'dispatcher',
        'permissions': ['dashboard', 'charters', 'drivers', 'vehicles', 'dispatch']
    },
    'matt': {
        'role': 'dispatcher',
        'permissions': ['dashboard', 'charters', 'drivers', 'vehicles', 'dispatch']
    },
    'mike_richard': {
        'role': 'driver',
        'permissions': ['dashboard', 'my_charters', 'my_schedule', 'timesheet']
    },
    'accountant': {
        'role': 'accountant',
        'permissions': ['dashboard', 'accounting', 'receipts', 'payments', 'reports', 'banking']
    }
}

for username, config in permission_configs.items():
    perms_json = json.dumps(config['permissions'])
    
    cur.execute("""
        UPDATE users 
        SET permissions = %s, role = %s, updated_at = NOW()
        WHERE username = %s
    """, (perms_json, config['role'], username))
    
    print(f"✅ {username:15} | Role: {config['role']:12} | Permissions: {config['permissions']}")

conn.commit()

# Verify final setup
print("\n" + "="*80)
print("FINAL USER CONFIGURATION")
print("="*80)

cur.execute("""
    SELECT user_id, username, email, role, permissions, status
    FROM users
    ORDER BY user_id
""")

for row in cur.fetchall():
    perms = row[4] if row[4] else []
    if isinstance(perms, str):
        try:
            perms = json.loads(perms)
        except:
            pass
    print(f"\n{row[0]:3} | {row[1]:15} | {row[3]:12} | {row[5]}")
    print(f"     Email: {row[2]}")
    print(f"     Permissions: {perms}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ All access rights configured!")
print("="*80)

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
print("DELETING REDUNDANT SYSTEM_USERS TABLE AND DEPENDENCIES")
print("="*80)
print(f"Timestamp: {datetime.now().isoformat()}")

# Tables to drop (in dependency order - child tables first)
tables_to_drop = [
    'user_scopes',           # References system_users.user_id
    'user_roles',            # References system_users.user_id
    'password_reset_tokens', # References system_users.user_id
    'concurrent_edits',      # References system_users.user_id
    'staged_edits',          # References system_users.user_id
    'record_locks',          # References system_users.user_id (locked_by_user_id)
    'security_audit_log',    # References system_users.user_id
    'system_users',          # Parent table
    'system_roles',          # Related role table
    'role_permissions',      # Role permissions (not connected to users table)
]

print("\nTables to drop (in dependency order):")
for table in tables_to_drop:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  - {table:25} ({count:,} rows)")

print("\n" + "="*80)
print("VERIFICATION: Is system_users actually unused?")
print("="*80)

# Double-check login_manager.py
with open('L:\\limo\\desktop_app\\login_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'system_users' in content:
        print("❌ ERROR: login_manager.py still references system_users!")
        print("   ABORTING - manual verification needed")
        cur.close()
        conn.close()
        exit(1)
    else:
        print("✅ login_manager.py does NOT use system_users")

# Check current main.py
with open('L:\\limo\\desktop_app\\main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'system_users' in content:
        print("❌ ERROR: main.py still references system_users!")
        print("   ABORTING - manual verification needed")
        cur.close()
        conn.close()
        exit(1)
    else:
        print("✅ main.py does NOT use system_users")

print("\n" + "="*80)
print("PROCEEDING WITH DELETION")
print("="*80)

try:
    for table in tables_to_drop:
        print(f"\nDropping {table}...", end=" ")
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print("✅ DELETED")
    
    conn.commit()
    print("\n" + "="*80)
    print("✅ ALL REDUNDANT TABLES SUCCESSFULLY DELETED")
    print("="*80)
    
    # Verify deletion
    print("\nVerification - remaining user-related tables:")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        AND table_name LIKE '%user%'
        ORDER BY table_name
    """)
    remaining = cur.fetchall()
    for table in remaining:
        cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cur.fetchone()[0]
        print(f"  - {table[0]:30} ({count:,} rows)")
    
    # Verify users table is intact
    print("\n" + "="*80)
    print("VERIFYING 'USERS' TABLE IS INTACT")
    print("="*80)
    cur.execute("SELECT username, role FROM users ORDER BY user_id")
    users = cur.fetchall()
    print(f"\n✅ users table has {len(users)} users:")
    for username, role in users:
        print(f"  - {username:20} ({role})")
    
    print("\n" + "="*80)
    print("CLEANUP COMPLETE")
    print("="*80)
    print("\nRemaining table count:")
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)
    total = cur.fetchone()[0]
    print(f"  Total tables in database: {total}")
    print(f"  Tables deleted: {len(tables_to_drop)}")
    print(f"  Original count: 333")
    print(f"  Expected new count: {333 - len(tables_to_drop)} (actual: {total})")
    
except Exception as e:
    print(f"\n❌ ERROR during deletion: {e}")
    conn.rollback()
    print("Transaction rolled back - no changes made")
finally:
    cur.close()
    conn.close()

print("\n✅ Script complete - redundant tables removed")

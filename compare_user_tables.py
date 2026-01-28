import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("COMPARING BOTH USER TABLES")
print("="*80)

print("\n1. SYSTEM_USERS TABLE (5 users):")
print("-" * 80)
cur.execute("""
    SELECT user_id, username, email, is_active
    FROM system_users
    ORDER BY user_id
""")
for row in cur.fetchall():
    print(f"  {row[0]:3} | {row[1]:15} | {row[2]:35} | Active: {row[3]}")

print("\n2. USERS TABLE (10 users):")
print("-" * 80)
cur.execute("""
    SELECT user_id, username, email, role, status
    FROM users
    ORDER BY user_id
""")
for row in cur.fetchall():
    print(f"  {row[0]:3} | {row[1]:15} | {row[2]:35} | Role: {row[3]:12} | {row[4]}")

# Check which table login_manager.py uses
print("\n" + "="*80)
print("CHECKING WHICH TABLE IS USED FOR AUTHENTICATION")
print("="*80)

import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

with open('L:\\limo\\desktop_app\\login_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'FROM system_users' in content:
        print("✅ login_manager.py uses: SYSTEM_USERS table")
    elif 'FROM users' in content:
        print("✅ login_manager.py uses: USERS table")
    else:
        print("⚠️  Could not determine which table is used")

cur.close()
conn.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("\nsystem_users: 5 users (paulr, matt, david, mikerichards, accountant)")
print("users:       10 users (admin, manager, dispatcher, paulr, disp, test, david, matt, mike_richard, accountant)")
print("\nNeed to check which table the desktop app actually uses for login!")

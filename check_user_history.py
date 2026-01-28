import psycopg2
from datetime import datetime

# Check database for any audit/changelog tables that might show user creation history
conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("CHECKING FOR USER CREATION HISTORY")
print("="*80)

# Check if there's an audit table or changelog
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND table_name LIKE '%audit%' OR table_name LIKE '%log%' OR table_name LIKE '%changelog%'
    ORDER BY table_name
""")

audit_tables = cur.fetchall()
if audit_tables:
    print("\nAudit/Log tables found:")
    for table in audit_tables:
        print(f"  - {table[0]}")
else:
    print("\nNo audit/log tables found")

# Check users table creation date and when records were added
print("\n" + "="*80)
print("Users table information:")
print("="*80)

cur.execute("""
    SELECT 
        table_name,
        to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') as checked_at
    FROM information_schema.tables
    WHERE table_name = 'users' AND table_schema = 'public'
""")
result = cur.fetchone()
if result:
    print(f"\nTable: {result[0]}")

# Check when users were created (via created_at column if it exists)
cur.execute("""
    SELECT 
        user_id,
        username,
        created_at,
        updated_at
    FROM users
    ORDER BY created_at
""")

rows = cur.fetchall()
print("\nUser creation timeline:")
for row in rows:
    created = row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else 'NULL'
    updated = row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'NULL'
    print(f"  {row[1]:15} | Created: {created} | Updated: {updated}")

# Check the last modification to users table
print("\n" + "="*80)
print("Checking for any DROP operations in history...")
print("="*80)
print("\nNote: PostgreSQL doesn't track dropped users without explicit audit logging.")
print("If david, mike, and matt were created and then deleted, they would be gone.")
print("\nMost likely: Those users were created in a test environment or migration")
print("that got rolled back, or they were never committed to this database.")

cur.close()
conn.close()

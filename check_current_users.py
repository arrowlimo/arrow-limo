import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("Current users in database:")
print("="*80)

cur.execute("SELECT user_id, username, email, role, status FROM users ORDER BY user_id")
rows = cur.fetchall()

for row in rows:
    print(f"{row[0]:3} | {row[1]:15} | {row[2]:30} | {row[3]:12} | {row[4]}")

print(f"\nTotal users: {len(rows)}")

# Check for the specific users mentioned
print("\n" + "="*80)
print("Searching for paulr, david, mike, matt:")
print("="*80)

specific_users = ['paulr', 'david', 'mike', 'matt']
for user in specific_users:
    cur.execute("SELECT user_id, username, email FROM users WHERE username ILIKE %s", (f'%{user}%',))
    result = cur.fetchone()
    if result:
        print(f"✅ Found '{user}': {result}")
    else:
        print(f"❌ '{user}' not found in users table")

cur.close()
conn.close()

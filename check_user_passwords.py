import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check if password_hash column exists
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'users'
    ORDER BY ordinal_position
""")
print("Users table columns:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print("\nUser password hashes:")
cur.execute("SELECT user_id, username, password_hash FROM users LIMIT 5")
for row in cur.fetchall():
    hash_status = "SET" if row[2] else "NULL"
    print(f"  {row[1]}: {hash_status}")

cur.close()
conn.close()

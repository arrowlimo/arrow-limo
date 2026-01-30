import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech'),
    database=os.environ.get('DB_NAME', 'neondb'),
    user=os.environ.get('DB_USER', 'neondb_owner'),
    password=os.environ.get('DB_PASSWORD', 'npg_89MbcFmZwUWo'),
    sslmode=os.environ.get('DB_SSLMODE', 'require')
)

cur = conn.cursor()

# Check matt user
cur.execute("""
    SELECT user_id, username, password_hash, role, status, email
    FROM users
    WHERE username = 'matt'
""")

result = cur.fetchone()
if result:
    user_id, username, pwd_hash, role, status, email = result
    print(f"User: {username}")
    print(f"  ID: {user_id}")
    print(f"  Role: {role}")
    print(f"  Status: {status}")
    print(f"  Email: {email}")
    print(f"  Password Hash: {pwd_hash[:50] if pwd_hash else 'NULL'}...")
    print(f"  Has password: {bool(pwd_hash)}")
else:
    print("User matt not found")

cur.close()
conn.close()

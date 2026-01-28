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
print("FIXING PAULR PASSWORD")
print("="*80)

# Update paulr password to correct one: halarin2026
password = "halarin2026"
password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

cur.execute("""
    UPDATE users 
    SET password_hash = %s, updated_at = NOW()
    WHERE username = 'paulr'
    RETURNING user_id, username, email
""", (password_hash,))

result = cur.fetchone()
if result:
    print(f"✅ Updated paulr (ID: {result[0]}) → halarin2026")
    print(f"   Email: {result[1]}")
else:
    print("❌ paulr user not found")

conn.commit()

# Verify the password works
cur.execute("SELECT password_hash FROM users WHERE username = 'paulr'")
stored_hash = cur.fetchone()[0]

if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
    print("✅ Password verification successful")
else:
    print("❌ Password verification failed")

cur.close()
conn.close()

print("\n" + "="*80)
print("UPDATED PASSWORD LIST")
print("="*80)
print("paulr / halarin2026")
print("david / richard2026")
print("matt / dispatcher1")
print("mike_richard / chauffeur")
print("accountant / 2025ArrowLimo")

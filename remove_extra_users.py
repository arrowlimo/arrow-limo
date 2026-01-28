import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("REMOVING USERS NOT IN APPROVED LIST")
print("="*80)

# Approved users to KEEP
keep_users = ['paulr', 'david', 'matt', 'mike_richard', 'accountant']

# Get current users
cur.execute("SELECT user_id, username, email, role FROM users ORDER BY user_id")
all_users = cur.fetchall()

print(f"\nCurrent users: {len(all_users)}")
for user_id, username, email, role in all_users:
    status = "✅ KEEP" if username in keep_users else "❌ DELETE"
    print(f"  {status} | {username:15} | {email:30} | {role}")

# Users to delete
users_to_delete = [u for u in all_users if u[1] not in keep_users]

if users_to_delete:
    print(f"\n" + "="*80)
    print(f"DELETING {len(users_to_delete)} USERS")
    print("="*80)
    
    for user_id, username, email, role in users_to_delete:
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        print(f"✅ Deleted: {username} (ID: {user_id})")
    
    conn.commit()
    print(f"\n✅ Deleted {len(users_to_delete)} users")
else:
    print("\nNo users to delete")

# Show final user list
print("\n" + "="*80)
print("FINAL USER LIST")
print("="*80)

cur.execute("SELECT user_id, username, email, role FROM users ORDER BY user_id")
final_users = cur.fetchall()

print(f"\nTotal users: {len(final_users)}\n")
for user_id, username, email, role in final_users:
    print(f"{user_id:2} | {username:15} | {email:30} | {role}")

cur.close()
conn.close()

print("\n" + "="*80)
print("CURRENT PASSWORDS")
print("="*80)
print("paulr / halarin2026")
print("david / richard2026")
print("matt / dispatcher1")
print("mike_richard / chauffeur")
print("accountant / 2025ArrowLimo")

"""
Verify database connection - checking if we're on local almsdata or Neon
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

print("=" * 70)
print("DATABASE CONNECTION VERIFICATION")
print("=" * 70)

print(f"\nConnection Settings:")
print(f"  DB_HOST:     {DB_HOST}")
print(f"  DB_NAME:     {DB_NAME}")
print(f"  DB_USER:     {DB_USER}")
print(f"  DB_PASSWORD: {'*' * len(DB_PASSWORD)}")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get database server version and name
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    
    cur.execute("SELECT current_database();")
    current_db = cur.fetchone()[0]
    
    cur.execute("SELECT inet_server_addr();")
    server_addr = cur.fetchone()[0]
    
    print(f"\n✓ Connection Successful!")
    print(f"\nDatabase Info:")
    print(f"  Current Database: {current_db}")
    print(f"  Server Address:   {server_addr}")
    print(f"  Version:          {version.split(',')[0]}")
    
    # Check if this looks like local or Neon
    if 'localhost' in DB_HOST or '127.0.0.1' in DB_HOST:
        print(f"\n🟢 CONFIRMED: Working on LOCAL almsdata database")
    elif 'neon' in DB_HOST.lower() or 'aws' in DB_HOST.lower():
        print(f"\n🔴 WARNING: Connected to REMOTE database (Neon/Cloud)")
    else:
        print(f"\n🟡 UNCLEAR: Host is {DB_HOST}")
    
    # Count records to verify data
    cur.execute("SELECT COUNT(*) FROM users;")
    user_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM charters;")
    charter_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM payments;")
    payment_count = cur.fetchone()[0]
    
    print(f"\nData Snapshot:")
    print(f"  Users:    {user_count}")
    print(f"  Charters: {charter_count}")
    print(f"  Payments: {payment_count}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n✗ Connection Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)

#!/usr/bin/env python3
"""Set up test user credentials for login testing"""

import bcrypt
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Neon credentials
db_host = os.environ.get('DB_HOST')
db_user = os.environ.get('DB_USER')
db_password = os.environ.get('DB_PASSWORD')
db_name = os.environ.get('DB_NAME')

# Test password
test_password = "test123"
password_hash = bcrypt.hashpw(test_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print(f"Test password: {test_password}")
print(f"Bcrypt hash: {password_hash}")

# Connect and update users
try:
    conn = psycopg2.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        sslmode='require'
    )
    cur = conn.cursor()
    
    # Update test user password
    cur.execute("""
        UPDATE users 
        SET password_hash = %s, status = 'active'
        WHERE username = 'test'
    """, (password_hash,))
    
    conn.commit()
    print(f"\n✅ Updated 'test' user with password hash")
    print(f"Login: username='test', password='{test_password}'")
    
    # Verify it worked
    cur.execute("""
        SELECT username, role, status FROM users WHERE username = 'test'
    """)
    row = cur.fetchone()
    if row:
        print(f"✅ Verified: {row[0]} | {row[1]} | {row[2]}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")

#!/usr/bin/env python3
"""Reset test user passwords with correct bcrypt hashes"""
import bcrypt
import psycopg2
from datetime import datetime

# Test credentials
TEST_USERS = {
    'paulr': 'TestPassword123!',
    'david': 'TestPassword123!',
    'matt': 'TestPassword123!',
    'mike_richard': 'TestPassword123!',
    'accountant': 'TestPassword123!',
}

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("Resetting test user passwords with bcrypt hashing...")
for username, password in TEST_USERS.items():
    # Hash the password with bcrypt (12 rounds = ~100ms)
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    
    # Update database
    cur.execute('''
        UPDATE users 
        SET password_hash = %s, 
            failed_login_attempts = 0,
            locked_until = NULL,
            updated_at = NOW()
        WHERE username = %s
    ''', (password_hash, username))
    
    print(f"  {username}:")
    print(f"    Password: {password}")
    print(f"    New hash: {password_hash}")
    print()

conn.commit()
cur.close()
conn.close()

print("Done! All passwords reset.")
print("\nTest credentials:")
for username in TEST_USERS:
    print(f"  {username} / TestPassword123!")

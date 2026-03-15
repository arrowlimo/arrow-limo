"""List all users and their current status"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )
    
    cur = conn.cursor()
    
    cur.execute("""
        SELECT user_id, username, email, role, status, 
               CASE WHEN password_hash IS NOT NULL THEN 'Yes' ELSE 'No' END as has_password
        FROM users 
        ORDER BY user_id;
    """)
    
    users = cur.fetchall()
    print(f"Total users: {len(users)}\n")
    print("-" * 80)
    for user in users:
        print(f"ID: {user[0]:3d} | Username: {user[1]:15s} | Email: {user[2]:35s}")
        print(f"         Role: {user[3]:15s} | Status: {user[4]:10s} | Password: {user[5]}")
        print("-" * 80)
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")

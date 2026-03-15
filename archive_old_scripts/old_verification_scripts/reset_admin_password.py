"""Reset admin password to a known value"""
import os
from dotenv import load_dotenv
import psycopg2
import bcrypt

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
    
    # Set new password
    new_password = "admin123"
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Update admin user
    cur.execute("""
        UPDATE users 
        SET password_hash = %s
        WHERE username = 'admin'
        RETURNING user_id, username, role;
    """, (password_hash,))
    
    result = cur.fetchone()
    if result:
        conn.commit()
        print(f"✅ Password reset successful!")
        print(f"   User ID: {result[0]}")
        print(f"   Username: {result[1]}")
        print(f"   Role: {result[2]}")
        print(f"   New Password: {new_password}")
    else:
        print("❌ No admin user found")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

"""Force reset admin password with detailed output"""
import os
from dotenv import load_dotenv
import psycopg2
import bcrypt

load_dotenv()

print("Starting password reset...")
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"DB_NAME: {os.getenv('DB_NAME')}")
print(f"DB_USER: {os.getenv('DB_USER')}")
print(f"DB_PORT: {os.getenv('DB_PORT')}")

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )
    print("✅ Connected to database")
    
    cur = conn.cursor()
    
    # Set new password
    new_password = "admin123"
    print(f"\nGenerating bcrypt hash for password: {new_password}")
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"Hash generated: {password_hash[:20]}...")
    
    # Update admin user
    print("\nUpdating admin user...")
    cur.execute("""
        UPDATE users 
        SET password_hash = %s
        WHERE username = 'admin'
        RETURNING user_id, username, role;
    """, (password_hash,))
    
    result = cur.fetchone()
    if result:
        print(f"✅ Password updated in database")
        print(f"   User ID: {result[0]}")
        print(f"   Username: {result[1]}")
        print(f"   Role: {result[2]}")
        
        # COMMIT the transaction
        conn.commit()
        print("✅ Transaction committed")
        
        # Verify the update
        cur.execute("SELECT password_hash FROM users WHERE username = 'admin';")
        verify = cur.fetchone()
        if verify:
            print(f"\nVerification - Hash in DB: {verify[0][:20]}...")
            
            # Test the password
            test_result = bcrypt.checkpw(new_password.encode('utf-8'), verify[0].encode('utf-8'))
            print(f"Password verification test: {test_result}")
            
            if test_result:
                print(f"\n✅ SUCCESS! Password is now: {new_password}")
            else:
                print("\n❌ FAILED! Password verification failed")
        
    else:
        print("❌ No admin user found")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

import psycopg2
import os

try:
    # Try localhost first (local database)
    try:
        conn = psycopg2.connect(
            host='localhost',
            database='almsdata',
            user='postgres',
            password='',
            sslmode='disable',
            connect_timeout=3
        )
        print("Connected to LOCAL database")
    except:
        # Try Neon (if available via env)
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech'),
            database=os.environ.get('DB_NAME', 'neondb'),
            user=os.environ.get('DB_USER', 'neondb_owner'),
            password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
            sslmode=os.environ.get('DB_SSLMODE', 'require')
        )
        print("Connected to NEON database")
    
    cur = conn.cursor()
    
    # Check if users table exists
    cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='users')")
    exists = cur.fetchone()[0]
    print(f"Users table exists: {exists}")
    
    if exists:
        # Get columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        print("\nUsers table schema:")
        for col, dtype in cur.fetchall():
            print(f"  {col}: {dtype}")
            
        # Check for sample users
        cur.execute("SELECT user_id, username, role FROM users LIMIT 5")
        print("\nSample users:")
        for row in cur.fetchall():
            print(f"  {row}")
    else:
        print("\nUsers table does NOT exist")
        print("Looking for employees table instead:")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'employees'
            LIMIT 10
        """)
        for col, dtype in cur.fetchall():
            print(f"  {col}: {dtype}")
    
    cur.close()
    conn.close()
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()

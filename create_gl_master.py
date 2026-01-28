"""
Create a master GL codes table with descriptions
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

try:
    # Create GL master table
    cur.execute("""
    DROP TABLE IF EXISTS gl_code_master CASCADE
    """)
    
    cur.execute("""
    CREATE TABLE gl_code_master (
        gl_code VARCHAR(20) PRIMARY KEY,
        description VARCHAR(500),
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    
    # Get all distinct GL codes from receipts
    cur.execute("""
    SELECT DISTINCT gl_account_code
    FROM receipts
    WHERE gl_account_code IS NOT NULL AND gl_account_code != ''
    ORDER BY gl_account_code
    """)
    
    gl_codes = cur.fetchall()
    print(f"Found {len(gl_codes)} distinct GL codes")
    
    # Insert with placeholder descriptions
    for code_tuple in gl_codes:
        code = code_tuple[0]
        cur.execute("""
        INSERT INTO gl_code_master (gl_code, description)
        VALUES (%s, %s)
        """, (code, f"GL Account {code}"))
        print(f"  {code}")
    
    conn.commit()
    print(f"\n✅ Created gl_code_master table with {len(gl_codes)} codes")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()

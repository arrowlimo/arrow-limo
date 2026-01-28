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

# Check for GL tables
cur.execute("""
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE '%gl%'
ORDER BY table_name
""")
tables = cur.fetchall()
print("GL-related tables:")
for t in tables:
    print(f"  - {t[0]}")

# Check gl_codes structure
print("\ngl_codes structure:")
cur.execute("""
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'gl_codes'
ORDER BY ordinal_position
""")
for col in cur.fetchall():
    print(f"  {col[0]}: {col[1]}")

# Check if gl_descriptions exists
try:
    print("\ngl_descriptions structure:")
    cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'gl_descriptions'
    ORDER BY ordinal_position
    """)
    for col in cur.fetchall():
        print(f"  {col[0]}: {col[1]}")
except:
    print("gl_descriptions not found")

# Show sample data
print("\nSample GL codes:")
cur.execute("SELECT * FROM gl_codes LIMIT 5")
for row in cur.fetchall():
    print(f"  {row}")

cur.close()
conn.close()

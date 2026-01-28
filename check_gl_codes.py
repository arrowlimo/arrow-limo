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

# Check if there's a GL master table
cur.execute("""
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE '%gl%'
""")
tables = cur.fetchall()
print("GL-related tables:", tables)

# Check receipts for actual GL codes used
cur.execute("""
SELECT DISTINCT gl_account_code 
FROM receipts 
WHERE gl_account_code IS NOT NULL
ORDER BY gl_account_code
LIMIT 20
""")
codes = cur.fetchall()
print("\nGL codes in receipts:")
for c in codes:
    print(f"  {c[0]}")

cur.close()
conn.close()

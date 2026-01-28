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

# Check gl_transactions structure
print("gl_transactions columns:")
cur.execute("""
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'gl_transactions'
ORDER BY ordinal_position
LIMIT 15
""")
for col in cur.fetchall():
    print(f"  {col[0]}: {col[1]}")

print("\nSample gl_transactions:")
cur.execute("SELECT * FROM gl_transactions LIMIT 3")
for row in cur.fetchall():
    print(f"  {row}")

print("\nDistinct GL codes in receipts:")
cur.execute("""
SELECT DISTINCT gl_account_code 
FROM receipts 
WHERE gl_account_code IS NOT NULL
ORDER BY gl_account_code
LIMIT 20
""")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()

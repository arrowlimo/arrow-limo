import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Check columns in gl_transactions
cur.execute("""
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'gl_transactions'
ORDER BY ordinal_position
""")
cols = cur.fetchall()
print("gl_transactions columns:")
for c in cols:
    print(f"  {c[0]}")

cur.close()
conn.close()

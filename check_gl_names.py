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

# Check gl_transactions table for descriptions
cur.execute("""
SELECT DISTINCT account_code, account_name FROM gl_transactions 
WHERE account_code IS NOT NULL
ORDER BY account_code
LIMIT 20
""")
rows = cur.fetchall()
print("GL codes with account_name from gl_transactions:")
for code, name in rows:
    print(f"  {code}: {name}")

cur.close()
conn.close()

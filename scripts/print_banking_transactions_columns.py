import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()
cur.execute("""
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema='public' AND table_name='banking_transactions' 
ORDER BY ordinal_position
""")
rows = cur.fetchall()
for name, dtype in rows:
    print(f"{name}: {dtype}")
cur.close()
conn.close()

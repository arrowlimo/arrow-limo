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

# Get distinct payment methods
cur.execute("""
SELECT DISTINCT payment_method FROM receipts 
ORDER BY payment_method
""")
methods = cur.fetchall()
print("Payment methods in database:")
for m in methods:
    print(f"  - {m[0]}")

cur.close()
conn.close()

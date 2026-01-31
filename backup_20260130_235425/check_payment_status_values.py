import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

cur.execute("SELECT DISTINCT status, COUNT(*) FROM payments GROUP BY status ORDER BY COUNT(*) DESC")
rows = cur.fetchall()

print("Payment status values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]} payments")

cur.close()
conn.close()

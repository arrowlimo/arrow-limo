import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employee_t4_summary' ORDER BY ordinal_position")
print("employee_t4_summary columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()

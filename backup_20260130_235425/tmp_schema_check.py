import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get all column names from receipts
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'receipts' ORDER BY ordinal_position")
columns = [row[0] for row in cur.fetchall()]

print("Receipt table columns:")
for col in columns:
    print(f"  - {col}")

# Get all column names from charters
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'charters' ORDER BY ordinal_position")
cols2 = [row[0] for row in cur.fetchall()]

print("\nCharters table columns:")
for col in cols2:
    print(f"  - {col}")

cur.close()
conn.close()

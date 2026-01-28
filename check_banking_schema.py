import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Check banking_transactions columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")

print("banking_transactions columns:")
for col_name, col_type in cur.fetchall():
    print(f"  {col_name}: {col_type}")

cur.close()
conn.close()

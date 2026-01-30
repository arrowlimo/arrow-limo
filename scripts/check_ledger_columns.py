import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_receipt_matching_ledger'
    ORDER BY ordinal_position
""")

print("=== banking_receipt_matching_ledger columns ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check a sample row
cur.execute("SELECT * FROM banking_receipt_matching_ledger LIMIT 1")
cols = [desc[0] for desc in cur.description]
row = cur.fetchone()
print(f"\n=== Sample row ===")
print(f"Columns: {cols}")
if row:
    print(f"Values: {row}")

cur.close()
conn.close()

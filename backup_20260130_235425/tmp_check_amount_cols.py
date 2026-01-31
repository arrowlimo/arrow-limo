import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get all column names
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'receipts' ORDER BY ordinal_position")
columns = [row[0] for row in cur.fetchall()]

# Find amount-related columns
amount_cols = [c for c in columns if 'amount' in c.lower() or 'total' in c.lower() or 'cost' in c.lower()]
print("Amount-related columns in receipts:")
for col in amount_cols:
    print(f"  - {col}")

# Sample 2019 receipt
print("\nSample 2019 receipt (first):") 
cur.execute("SELECT receipt_id, vendor_name, receipt_date FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2019 LIMIT 1")
receipt_id, vendor, date = cur.fetchone()
print(f"Receipt ID {receipt_id}, Vendor: {vendor}, Date: {date}")

# Check which amount column exists for this receipt
print("\nAmount column values for this receipt:")
cur.execute(f"""
    SELECT receipt_id, amount, amount_due, total_amount_due, receipt_total 
    FROM receipts WHERE receipt_id = {receipt_id}
""")
result = cur.fetchone()
print(f"Result: {result}")

cur.close()
conn.close()

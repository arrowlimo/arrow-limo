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

# Get receipt #140678
cur.execute("""
SELECT receipt_id, vendor_name, gross_amount, payment_method 
FROM receipts 
WHERE receipt_id = 140678
""")
result = cur.fetchone()
if result:
    print(f"Receipt {result[0]}: {result[1]} ${result[2]} - Payment: {result[3]}")
else:
    print("Receipt not found")

cur.close()
conn.close()

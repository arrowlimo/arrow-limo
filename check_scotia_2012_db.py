import psycopg2
import os

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check column names
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='receipts' ORDER BY ordinal_position")
print("RECEIPTS TABLE COLUMNS:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check Scotia 2012 data
print("\n" + "=" * 80)
print("SCOTIA BANK 2012 RECEIPTS IN DATABASE")
print("=" * 80)
cur.execute("""
    SELECT COUNT(*) as total, 
           MIN(receipt_date) as earliest_date,
           MAX(receipt_date) as latest_date,
           SUM(CAST(receipt_amount AS DECIMAL)) as total_amount,
           COUNT(DISTINCT vendor_name) as unique_vendors
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
""")
result = cur.fetchone()
print(f"Total receipts: {result[0]}")
print(f"Earliest date: {result[1]}")
print(f"Latest date: {result[2]}")
print(f"Total amount: ${result[3]:,.2f}" if result[3] else "Total amount: $0.00")
print(f"Unique vendors: {result[4]}")

# Check creation dates
print("\n" + "=" * 80)
print("RECEIPT CREATION DATES (Scotia 2012)")
print("=" * 80)
cur.execute("""
    SELECT DATE(created_at) as import_date, COUNT(*) as count
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
    GROUP BY DATE(created_at)
    ORDER BY import_date DESC
""")
for row in cur.fetchall():
    print(f"Imported on {row[0]}: {row[1]} receipts")

cur.close()
conn.close()

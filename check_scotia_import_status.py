import psycopg2
import os

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("SCOTIA 2012 RECEIPT DATA STATUS CHECK")
print("=" * 80)

# How many Scotia 2012 receipts
cur.execute("""
    SELECT COUNT(*) FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
""")
count = cur.fetchone()[0]
print(f"\nTotal Scotia 2012 receipts in DB: {count}")

# When were they created
cur.execute("""
    SELECT DATE(created_at) as import_date, COUNT(*) as count
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
    GROUP BY DATE(created_at)
    ORDER BY import_date DESC
""")
print("\nImport dates:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} receipts")

# Check if they were updated recently
cur.execute("""
    SELECT DATE(updated_at) as update_date, COUNT(*) as count
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
    GROUP BY DATE(updated_at)
    ORDER BY update_date DESC
""")
print("\nUpdate dates (last 5):")
rows = cur.fetchall()
for row in rows[:5]:
    print(f"  {row[0]}: {row[1]} receipts")

# Show sample records
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, receipt_amount, created_at, updated_at
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND mapped_bank_account_id = 2
    ORDER BY receipt_date ASC
    LIMIT 5
""")
print("\nSample records (first 5):")
for row in cur.fetchall():
    print(f"  ID {row[0]} | {row[1]} | {row[2]} | {row[3]} | Created: {row[4]} | Updated: {row[5]}")

cur.close()
conn.close()

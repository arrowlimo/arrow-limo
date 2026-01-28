import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)

cur = conn.cursor()

# Check Wix receipts
cur.execute("""
    SELECT vendor_name, COUNT(*) as cnt, SUM(gross_amount) as total, 
           MIN(receipt_date), MAX(receipt_date)
    FROM receipts 
    WHERE vendor_name LIKE 'Wix%'
    GROUP BY vendor_name
    ORDER BY vendor_name
""")

print("Existing Wix receipts in database:")
print("-" * 80)
for row in cur.fetchall():
    vendor, cnt, total, min_date, max_date = row
    print(f"{vendor:40} {cnt:4d}  ${total:10,.2f}  [{min_date} to {max_date}]")

# Count total
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name LIKE 'Wix%'")
total_cnt, total_amt = cur.fetchone()
print("-" * 80)
print(f"{'TOTAL':40} {total_cnt:4d}  ${total_amt:10,.2f}")

conn.close()

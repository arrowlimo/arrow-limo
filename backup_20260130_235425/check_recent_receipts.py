import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("Most recent Welcome Wagon receipts (by receipt_id):")
print("=" * 80)
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           description, created_at
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome%' 
       OR description ILIKE '%welcome%'
    ORDER BY receipt_id DESC 
    LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    print(f"ID: {r[0]}")
    print(f"  Date: {r[1]}")
    print(f"  Vendor: {r[2]}")
    print(f"  Amount: ${r[3]}")
    print(f"  Description: {r[4]}")
    print(f"  Created At: {r[5]}")
    print()

print("\nMost recent receipts added (last 5):")
print("=" * 80)
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           description, created_at
    FROM receipts 
    ORDER BY created_at DESC NULLS LAST, receipt_id DESC
    LIMIT 5
""")
rows = cur.fetchall()
for r in rows:
    print(f"ID: {r[0]}")
    print(f"  Date: {r[1]}")
    print(f"  Vendor: {r[2]}")
    print(f"  Amount: ${r[3]}")
    print(f"  Created At: {r[5]}")
    print()

conn.close()

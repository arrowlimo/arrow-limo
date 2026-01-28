"""
Check for Fibrenew receipts in February 2024, especially looking for $300 receipt on Feb 20, 2024.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("\n=== Fibrenew receipts in February 2024 ===\n")

# Get all February 2024 Fibrenew receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
    AND receipt_date >= '2024-02-01'
    AND receipt_date <= '2024-02-29'
    ORDER BY receipt_date
""")

feb_receipts = cur.fetchall()

print(f"Total Fibrenew receipts in February 2024: {len(feb_receipts)}\n")

if feb_receipts:
    for r in feb_receipts:
        print(f"{r[1]} | ${r[3]:>10,.2f} | {r[4][:70]}")
else:
    print("No Fibrenew receipts found in February 2024")

# Check specifically for $300 on Feb 20, 2024
print("\n=== Checking for $300 receipt on Feb 20, 2024 ===\n")

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, category
    FROM receipts
    WHERE receipt_date = '2024-02-20'
    AND gross_amount = 300.00
""")

feb20_300 = cur.fetchall()

if feb20_300:
    print(f"Found {len(feb20_300)} receipt(s) for $300 on Feb 20, 2024:")
    for r in feb20_300:
        print(f"  {r[2]} | ${r[3]:,.2f} | Category: {r[5]} | {r[4][:60]}")
else:
    print("No $300 receipt found on Feb 20, 2024")

# Check all 2024 Fibrenew receipts to see what we have
print("\n=== All 2024 Fibrenew receipts ===\n")

cur.execute("""
    SELECT receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
    AND receipt_date >= '2024-01-01'
    AND receipt_date <= '2024-12-31'
    ORDER BY receipt_date
""")

all_2024 = cur.fetchall()
print(f"Total 2024 Fibrenew receipts: {len(all_2024)}\n")

for r in all_2024:
    print(f"{r[0]} | ${r[1]:>10,.2f} | {r[2][:60]}")

cur.close()
conn.close()

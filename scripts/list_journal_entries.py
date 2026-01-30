import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("Journal Entries and Adjustments in Receipts:\n")

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, source_system 
    FROM receipts 
    WHERE description ILIKE '%journal%' 
       OR vendor_name ILIKE '%journal%' 
       OR description ILIKE '%adjustment%'
    ORDER BY receipt_date
""")

print(f"{'ID':<10} {'Date':<12} {'Vendor':<25} {'Amount':>12} {'Description'}")
print("-" * 100)

for row in cur.fetchall():
    receipt_id, date, vendor, desc, amount, source = row
    vendor_str = (vendor or 'NULL')[:23]
    desc_str = (desc or '')[:50]
    amt = amount if amount else 0
    print(f"{receipt_id:<10} {date} {vendor_str:<25} ${amt:>10,.2f} {desc_str}")

print("\nThese should be removed from receipts table (they're accounting adjustments, not actual receipts)")

cur.close()
conn.close()

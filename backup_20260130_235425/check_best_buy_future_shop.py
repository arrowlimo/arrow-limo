import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check Best Buy and Future Shop receipts
cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        gl_account_name,
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%best buy%'
       OR LOWER(vendor_name) LIKE '%future shop%'
    GROUP BY vendor_name, gl_account_code, gl_account_name, category
    ORDER BY vendor_name, count DESC
""")

print("Best Buy / Future Shop Receipts:")
print(f"{'Vendor':<50} {'GL Code':<10} {'GL Name':<40} {'Category':<25} {'Count':>6} {'Amount':>12}")
print("-" * 145)

rows = cur.fetchall()
total_count = 0
total_amount = 0

for r in rows:
    total_count += r[4]
    total_amount += r[5] or 0
    print(f"{r[0][:49]:<50} {str(r[1] or 'NULL'):<10} {str(r[2] or '')[:39]:<40} {str(r[3] or '')[:24]:<25} {r[4]:>6} ${r[5]:>11,.2f}")

print("-" * 145)
print(f"Total: {total_count} receipts, ${total_amount:,.2f}")

# Check if any are NOT GL 6400 (Office Supplies)
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE (LOWER(vendor_name) LIKE '%best buy%' OR LOWER(vendor_name) LIKE '%future shop%')
      AND (gl_account_code != '6400' OR gl_account_code IS NULL)
""")

wrong_count, wrong_amount = cur.fetchone()
if wrong_count > 0:
    print(f"\n⚠️  {wrong_count} receipts need GL code update to 6400 (Office Supplies) - ${wrong_amount:,.2f}")
else:
    print("\n✅ All Best Buy/Future Shop receipts already have correct GL code 6400")

# Show distinct vendor names
print("\n" + "="*80)
print("Distinct vendor names:")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%best buy%'
       OR LOWER(vendor_name) LIKE '%future shop%'
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
""")

for r in cur.fetchall():
    print(f"  {r[0]:<60} {r[1]:>4} receipts, ${r[2]:>11,.2f}")

cur.close()
conn.close()

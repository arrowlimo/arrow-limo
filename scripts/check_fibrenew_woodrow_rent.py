import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check Fibrenew and Woodrow receipts
cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        gl_account_name,
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
       OR LOWER(vendor_name) LIKE '%woodrow%'
    GROUP BY vendor_name, gl_account_code, gl_account_name, category
    ORDER BY vendor_name, count DESC
""")

print("Fibrenew / Woodrow Receipts:")
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

# Check what GL code should be used for rent
print("\n" + "="*80)
print("Checking existing rent GL codes in database...")
cur.execute("""
    SELECT DISTINCT gl_account_code, gl_account_name
    FROM receipts
    WHERE LOWER(gl_account_name) LIKE '%rent%'
       OR LOWER(category) LIKE '%rent%'
    ORDER BY gl_account_code
""")

print("\nExisting Rent GL codes:")
for r in cur.fetchall():
    print(f"  GL {r[0]}: {r[1]}")

# Show distinct vendor names
print("\n" + "="*80)
print("Distinct vendor names:")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
       OR LOWER(vendor_name) LIKE '%woodrow%'
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
""")

for r in cur.fetchall():
    print(f"  {r[0]:<60} {r[1]:>4} receipts, ${r[2]:>11,.2f}")

# Check how many need updating (assuming GL 6100 for rent)
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE (LOWER(vendor_name) LIKE '%fibrenew%' OR LOWER(vendor_name) LIKE '%woodrow%')
      AND (gl_account_code != '6100' OR gl_account_code IS NULL)
""")

wrong_count, wrong_amount = cur.fetchone()
if wrong_count > 0:
    print(f"\n⚠️  {wrong_count} receipts may need GL code update to 6100 (Rent) - ${wrong_amount:,.2f}")

cur.close()
conn.close()

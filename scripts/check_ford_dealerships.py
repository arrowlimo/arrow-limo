import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check Ford dealership receipts
cur.execute("""
    SELECT 
        vendor_name,
        gl_account_code,
        gl_account_name,
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%ford%'
    GROUP BY vendor_name, gl_account_code, gl_account_name, category
    ORDER BY count DESC
""")

print("Ford Dealership Receipts:")
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

# Check if any are NOT GL 5100
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%ford%'
      AND (gl_account_code != '5100' OR gl_account_code IS NULL)
""")

wrong_count, wrong_amount = cur.fetchone()
if wrong_count > 0:
    print(f"\n⚠️  {wrong_count} Ford receipts need GL code update (${wrong_amount:,.2f})")
else:
    print("\n✅ All Ford dealership receipts already have correct GL code 5100")

cur.close()
conn.close()

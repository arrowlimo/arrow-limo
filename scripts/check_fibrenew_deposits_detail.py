import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check FIBRENEW GL 4110 receipts in detail
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        gl_account_code,
        description
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
      AND gl_account_code = '4110'
    ORDER BY receipt_date
""")

print("FIBRENEW GL 4110 (Customer Deposits) - Should be Rent except 2 wedding trades:")
print(f"{'ID':<8} {'Date':<12} {'Vendor':<30} {'Amount':>12} {'Description':<50}")
print("-" * 125)

rows = cur.fetchall()
for r in rows:
    desc = (r[5] or '')[:49]
    print(f"{r[0]:<8} {str(r[1]):<12} {r[2][:29]:<30} ${r[3]:>11,.2f} {desc:<50}")

print(f"\nTotal: {len(rows)} receipts")

# Check if any mention wedding
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
      AND gl_account_code = '4110'
      AND (LOWER(description) LIKE '%wedding%' 
           OR LOWER(description) LIKE '%trade%')
""")

wedding_rows = cur.fetchall()
print("\n" + "="*80)
print("Receipts mentioning 'wedding' or 'trade':")
if wedding_rows:
    for r in wedding_rows:
        print(f"  ID {r[0]} - {r[1]} - ${r[2]:,.2f} - {r[3] or ''}")
else:
    print("  None found with 'wedding' or 'trade' in description")

cur.close()
conn.close()

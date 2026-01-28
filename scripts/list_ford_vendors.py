import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get distinct vendor names containing "ford"
cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount,
        MIN(receipt_date) as first_date,
        MAX(receipt_date) as last_date
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%ford%'
    GROUP BY vendor_name
    ORDER BY total_amount DESC
""")

print("All vendors containing 'FORD':")
print(f"{'Vendor Name':<60} {'Count':>6} {'Total Amount':>15} {'First Date':<12} {'Last Date':<12}")
print("-" * 115)

rows = cur.fetchall()
for r in rows:
    print(f"{r[0][:59]:<60} {r[1]:>6} ${r[2]:>13,.2f} {str(r[3]):<12} {str(r[4]):<12}")

print(f"\nTotal: {len(rows)} distinct vendors")

cur.close()
conn.close()

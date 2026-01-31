import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        category,
        description,
        payment_method,
        check_number,
        banking_transaction_id,
        invoice_number
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%' 
    ORDER BY receipt_date, receipt_id
""")

rows = cur.fetchall()

print(f"{'ID':<10} {'Date':<12} {'Vendor':<30} {'Amount':<10} {'Method':<15} {'Check#':<10} {'Invoice#':<10} {'Banking ID'}")
print('-' * 140)

for r in rows:
    print(f"{r[0]:<10} {str(r[1]):<12} {r[2]:<30} {r[3]:>9.2f} {(r[6] or 'N/A'):<15} {(r[7] or 'N/A'):<10} {(r[9] or 'N/A'):<10} {r[8] or 'N/A'}")

print(f"\nTotal receipts found: {len(rows)}")

cur.close()
conn.close()

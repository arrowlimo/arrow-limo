import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Check for receipts linked to March 19 transactions
cur.execute("""
    SELECT 
        receipt_id, 
        receipt_date, 
        vendor_name, 
        gross_amount, 
        banking_transaction_id, 
        description,
        category,
        is_nsf
    FROM receipts 
    WHERE banking_transaction_id IN (57979, 81728)
    ORDER BY receipt_id
""")

rows = cur.fetchall()

print(f"Receipts for March 19 Welcome Wagon transactions (57979 and 81728):\n")

if rows:
    for r in rows:
        print(f"Receipt {r[0]}: {r[1]} - {r[2]} - ${r[3]:.2f}")
        print(f"  Banking TX: {r[4]}")
        print(f"  Description: {r[5] or 'N/A'}")
        print(f"  Category: {r[6] or 'N/A'}")
        print(f"  Is NSF: {r[7]}")
        print()
else:
    print("❌ NO RECEIPTS FOUND for March 19 transactions!")
    print("\nThis means receipts are MISSING for the successful re-payment.")

print("\n" + "="*80)
print("\nAll Welcome Wagon receipts currently in database:\n")

cur.execute("""
    SELECT 
        receipt_id, 
        receipt_date, 
        vendor_name, 
        gross_amount, 
        banking_transaction_id,
        is_nsf,
        description
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%'
    ORDER BY receipt_date, receipt_id
""")

all_rows = cur.fetchall()

for r in all_rows:
    print(f"Receipt {r[0]}: {r[1]} - {r[2]} - ${r[3]:.2f} - Banking TX: {r[4] or 'N/A'} - NSF: {r[5]}")

print(f"\nTotal Welcome Wagon receipts: {len(all_rows)}")
print("\n❌ MISSING: Receipt for March 19 re-payment (should link to TX 57979 or 81728)")

cur.close()
conn.close()

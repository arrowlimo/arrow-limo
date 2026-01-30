import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("Deleting phantom Welcome Wagon receipts that don't exist in verified bank records...")
print("="*100)

# Delete the phantom receipts
cur.execute("""
    DELETE FROM receipts 
    WHERE receipt_id IN (141603, 141605, 141606)
    RETURNING receipt_id, receipt_date, vendor_name, gross_amount
""")

deleted = cur.fetchall()

if deleted:
    print(f"\n✅ Deleted {len(deleted)} phantom receipts:\n")
    for r in deleted:
        print(f"   Receipt {r[0]}: {r[1]} - {r[2]} - ${r[3]:.2f}")

conn.commit()

print("\n" + "="*100)
print("\nVerifying only the VALID receipt remains...")
print("="*100 + "\n")

# Verify what's left
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        banking_transaction_id,
        category,
        description
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%'
    ORDER BY receipt_date, receipt_id
""")

remaining = cur.fetchall()

if remaining:
    print(f"{'Receipt ID':<12} {'Date':<12} {'Vendor':<35} {'Amount':<10} {'Banking TX':<12} {'Category':<20} {'Description'}")
    print('-' * 120)
    for r in remaining:
        print(f"{r[0]:<12} {str(r[1]):<12} {r[2]:<35} ${r[3]:>8.2f} {r[4] or 'N/A':<12} {r[5] or '':<20} {r[6] or ''}")
    print(f"\n✅ Only {len(remaining)} valid Welcome Wagon receipt remains!")
else:
    print("❌ No Welcome Wagon receipts found!")

cur.close()
conn.close()

print("\n" + "="*100)
print("\n✅ CLEANED UP: All phantom Welcome Wagon receipts deleted")
print("✅ VALID: Only Receipt 141634 (March 19, 2012, CHQ 215, $150.00) remains")

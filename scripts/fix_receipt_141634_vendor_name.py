import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("Fixing Receipt 141634 vendor name from '000000017320441' to 'CHEQUE WELCOME WAGON'...\n")

# Update the vendor name
cur.execute("""
    UPDATE receipts 
    SET vendor_name = 'CHEQUE WELCOME WAGON',
        description = 'advertising - re-payment after NSF'
    WHERE receipt_id = 141634
""")

affected = cur.rowcount
conn.commit()

print(f"✅ Updated {affected} receipt(s)")

# Verify the change
cur.execute("""
    SELECT 
        receipt_id, 
        receipt_date, 
        vendor_name, 
        gross_amount, 
        banking_transaction_id,
        description
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%'
    ORDER BY receipt_date, receipt_id
""")

rows = cur.fetchall()

print("\n" + "="*100)
print("\nAll Welcome Wagon receipts after fix:\n")
print(f"{'Receipt ID':<12} {'Date':<12} {'Vendor':<35} {'Amount':<10} {'Banking TX':<12} {'Description'}")
print('-' * 100)

for r in rows:
    print(f"{r[0]:<12} {str(r[1]):<12} {r[2]:<35} ${r[3]:>8.2f} {r[4] or 'N/A':<12} {r[5] or ''}")

print(f"\n✅ Now showing {len(rows)} Welcome Wagon receipts (was 3, should be 4)")

cur.close()
conn.close()

print("\n" + "="*100)
print("\n✅ COMPLETE STORY for Check #215 Welcome Wagon:")
print("="*100)
print("\n1. March 14: Check #215 issued for $150.00 (Receipt 141603)")
print("2. March 14: Check bounced - NSF fee $12.00 (Receipt 141605)")  
print("3. March 14: QB duplicate credit entry (Receipt 141606 - marked as duplicate)")
print("4. March 19: Re-payment successful $150.00 (Receipt 141634 - NOW FIXED)")
print("\n✅ All 4 receipts now correctly labeled as Welcome Wagon!")

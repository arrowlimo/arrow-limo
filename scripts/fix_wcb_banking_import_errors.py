"""
Fix WCB banking import errors - convert incorrectly imported invoices to payments
Two transactions were imported as invoices when they should be payments TO WCB
Amounts: $3,446.02 and $553.17
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Find the receipts with these specific amounts for WCB
print("=== Finding WCB Banking Import Errors ===\n")

cur.execute("""
    SELECT receipt_id, gross_amount, receipt_date, source_reference
    FROM receipts
    WHERE vendor_name ILIKE '%WCB%' 
    AND gross_amount IN (3446.02, 553.17)
    AND created_from_banking = true
    ORDER BY receipt_date
""")

incorrect_receipts = cur.fetchall()
print(f"Found {len(incorrect_receipts)} matching receipts:\n")

receipt_ids = []
for row in incorrect_receipts:
    print(f"Receipt ID: {row[0]}, Amount: ${row[1]:,.2f}, Date: {row[2]}, Ref: {row[3]}")
    receipt_ids.append(row[0])

if not receipt_ids:
    print("No matching receipts found!")
    conn.close()
    exit()

print("\n=== Checking Details ===\n")

for receipt_id in receipt_ids:
    cur.execute("""
        SELECT receipt_id, vendor_name, source_reference, receipt_date, 
               gross_amount, description, created_from_banking, banking_transaction_id
        FROM receipts 
        WHERE receipt_id = %s
    """, (receipt_id,))
    
    row = cur.fetchone()
    if row:
        print(f"Receipt ID: {row[0]}")
        print(f"Vendor: {row[1]}")
        print(f"Reference: {row[2]}")
        print(f"Date: {row[3]}")
        print(f"Amount: ${row[4]:,.2f}")
        print(f"Description: {row[5]}")
        print(f"Created from banking: {row[6]}")
        print(f"Banking TX ID: {row[7]}")
        
        # Check for linked payments
        cur.execute("SELECT COUNT(*) FROM banking_receipt_matching_ledger WHERE receipt_id = %s", (receipt_id,))
        links = cur.fetchone()[0]
        print(f"Banking links: {links}")
        print()

print("\n=== FIXING ===\n")

# Delete these incorrect invoice records
for receipt_id in receipt_ids:
    cur.execute("SELECT gross_amount, receipt_date FROM receipts WHERE receipt_id = %s", (receipt_id,))
    row = cur.fetchone()
    if row:
        amount, date = row
        
        # Delete banking links first
        cur.execute("DELETE FROM banking_receipt_matching_ledger WHERE receipt_id = %s", (receipt_id,))
        deleted_links = cur.rowcount
        
        # Delete the incorrect receipt
        cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
        deleted_receipts = cur.rowcount
        
        print(f"✅ Deleted receipt {receipt_id} (${amount:,.2f} on {date})")
        print(f"   - Removed {deleted_links} banking links")
        print(f"   - Removed {deleted_receipts} receipt record")
        print()

conn.commit()
print("\n✅ Changes committed successfully!")
print("\nNote: These were incorrectly imported as invoices FROM WCB.")
print("WCB is a vendor you pay, not a customer. These banking transactions")
print("represented payments TO WCB and should not have been in the receipts table.")

cur.close()
conn.close()

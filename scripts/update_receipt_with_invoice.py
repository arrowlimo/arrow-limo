#!/usr/bin/env python
"""
Update Banking-Imported Receipt with Invoice Details
For cases where you have the paper invoice but only a generic banking receipt exists
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

print("=" * 80)
print("UPDATE RECEIPT WITH INVOICE DETAILS")
print("=" * 80)

# Example: Update Receipt 140163 with Fibrenew invoice 5386 details
receipt_id = 140163
invoice_num = "5386"
invoice_date = "2013-03-03"
description = "Office rent - March 2013 - Invoice 5386"
category = "Office Rent"

print(f"\nCurrent Receipt Details:")
cur = conn.cursor()
cur.execute("""
    SELECT 
        receipt_id, receipt_date, vendor_name, gross_amount,
        description, source_reference, category, banking_transaction_id
    FROM receipts
    WHERE receipt_id = %s
""", (receipt_id,))
current = cur.fetchone()

if current:
    print(f"Receipt ID: {current[0]}")
    print(f"Date: {current[1]}")
    print(f"Vendor: {current[2]}")
    print(f"Amount: ${current[3]:,.2f}")
    print(f"Description: {current[4] or 'NONE'}")
    print(f"Invoice/Ref: {current[5] or 'NONE'}")
    print(f"Category: {current[6] or 'NONE'}")
    print(f"Banking ID: {current[7]}")
    
    print("\n" + "=" * 80)
    print("PROPOSED UPDATE:")
    print("=" * 80)
    print(f"Invoice Date: {current[1]} → {invoice_date}")
    print(f"Description: '{current[4] or 'NONE'}' → '{description}'")
    print(f"Invoice #: '{current[5] or 'NONE'}' → '{invoice_num}'")
    print(f"Category: '{current[6] or 'NONE'}' → '{category}'")
    
    # Uncomment to actually apply the update:
    """
    cur.execute('''
        UPDATE receipts
        SET 
            receipt_date = %s,
            description = %s,
            source_reference = %s,
            category = %s
        WHERE receipt_id = %s
    ''', (invoice_date, description, invoice_num, category, receipt_id))
    
    conn.commit()
    print("\n✅ UPDATE APPLIED")
    """
    
    print("\n⚠️  DRY RUN MODE - No changes made")
    print("To apply update, uncomment the UPDATE section in the script")
else:
    print(f"❌ Receipt {receipt_id} not found")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("ALTERNATIVE APPROACH:")
print("=" * 80)
print("If the $2,179.34 payment covered MULTIPLE invoices:")
print("1. Delete the generic receipt (140163)")
print("2. Create separate receipts for each invoice:")
print("   - Invoice 5386 - $650.00 (or actual amount)")
print("   - Invoice XXXX - $____")
print("   - Invoice YYYY - $____")
print("   All with same banking_transaction_id = 79797")
print("3. Total should equal $2,179.34")
print("=" * 80)

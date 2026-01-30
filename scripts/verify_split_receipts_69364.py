#!/usr/bin/env python
"""Verify the split receipts created for banking transaction 69364"""

import psycopg2

conn = psycopg2.connect('host=localhost user=postgres password=***REDACTED*** dbname=almsdata')
cur = conn.cursor()

print("✅ Verification of Split Receipts Created:\n")

cur.execute("""
SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, 
       description, gl_account_code, payment_method, banking_transaction_id
FROM receipts 
WHERE receipt_id IN (145330, 145331)
ORDER BY receipt_id
""")

for row in cur.fetchall():
    receipt_id, date, vendor, amount, gst, desc, gl, payment, banking = row
    print(f"Receipt #{receipt_id}:")
    print(f"  Date: {date}")
    print(f"  Vendor: {vendor}")
    print(f"  Amount: ${amount:.2f} (GST: ${gst:.2f})")
    print(f"  GL Code: {gl}")
    print(f"  Payment: {payment}")
    print(f"  Banking ID: {banking}")
    print(f"  Description: {desc}")
    print()

# Verify banking match
print("\n✅ Banking Matching Ledger:")
cur.execute("""
SELECT banking_transaction_id, receipt_id, match_type, match_status, notes
FROM banking_receipt_matching_ledger
WHERE receipt_id IN (145330, 145331)
ORDER BY receipt_id
""")

for row in cur.fetchall():
    banking_id, receipt_id, match_type, status, notes = row
    print(f"  Banking {banking_id} -> Receipt #{receipt_id}")
    print(f"    Type: {match_type}, Status: {status}")
    print(f"    Notes: {notes}")
    print()

cur.close()
conn.close()

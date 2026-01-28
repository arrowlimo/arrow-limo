#!/usr/bin/env python3
"""
Fix Receipt 145297 - should be fiscal_year 2011, not 2012
And verify we have the correct 2012-03-19 invoice ($1,126.80)
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("FIXING RECEIPT 145297 - DATE TYPO")
print("="*70)

# Check current state
cur.execute("""
    SELECT receipt_id, source_reference, receipt_date, invoice_date, gross_amount, 
           fiscal_year, description
    FROM receipts
    WHERE receipt_id = 145297
""")
row = cur.fetchone()

print("\nCurrent state:")
print(f"  Receipt ID: {row[0]}")
print(f"  Reference: {row[1]}")
print(f"  Receipt Date: {row[2]}")
print(f"  Invoice Date: {row[3]}")
print(f"  Amount: ${row[4]:,.2f}")
print(f"  Fiscal Year: {row[5]}")
print(f"  Description: {row[6]}")

# Update to fiscal_year 2011
print("\nUpdating fiscal_year to 2011...")
cur.execute("""
    UPDATE receipts
    SET fiscal_year = 2011
    WHERE receipt_id = 145297
""")

conn.commit()
print("✓ Updated")

# Now check if we have the 2012-03-19 $1,126.80 invoice
print("\n" + "="*70)
print("CHECKING FOR 2012-03-19 INVOICE ($1,126.80)")
print("="*70)

cur.execute("""
    SELECT receipt_id, source_reference, invoice_date, gross_amount, description
    FROM receipts
    WHERE vendor_name = 'WCB'
      AND invoice_date = '2012-03-19'
      AND ABS(gross_amount - 1126.80) < 0.01
""")

result = cur.fetchone()
if result:
    print(f"\n✓ Found: Receipt {result[0]} | Ref {result[1]} | ${result[3]:,.2f}")
else:
    print("\n✗ NOT FOUND - need to add this invoice")
    print("   Should be: 2012-03-19, Ref 18254521, $1,126.80")

# Show new 2012 totals
print("\n" + "="*70)
print("NEW 2012 TOTALS (after fiscal_year fix)")
print("="*70)

cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
count, total = cur.fetchone()

print(f"\n2012 Invoices: {count} = ${total:,.2f}")

cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2011 AND gross_amount > 0
""")
count, total = cur.fetchone()

print(f"2011 Invoices: {count} = ${total:,.2f}")

conn.close()

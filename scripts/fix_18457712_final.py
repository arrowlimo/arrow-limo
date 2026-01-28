#!/usr/bin/env python3
"""
Fix 18457712 duplicate:
- Delete Receipt 145298 (not linked, date 2012-06-01)
- Keep Receipt 145294 (linked to banking 69282) but fix date to 2012-06-01
"""

import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("FIXING 18457712 DUPLICATE")
print("="*70)

# Delete Receipt 145298 (not banking-linked, so it's the duplicate)
print("\n1. Deleting Receipt 145298 (non-linked duplicate)...")
cur.execute("""
    DELETE FROM receipts
    WHERE receipt_id = 145298
    RETURNING receipt_id, receipt_date, gross_amount
""")
deleted = cur.fetchone()
if deleted:
    print(f"   ✅ Deleted: Receipt {deleted[0]} | {deleted[1]} | ${deleted[2]:,.2f}")

# Update Receipt 145294 date from 2012-06-19 to 2012-06-01 to match Excel
print("\n2. Updating Receipt 145294 date to match Excel...")
cur.execute("""
    UPDATE receipts
    SET receipt_date = '2012-06-01',
        invoice_date = '2012-06-01'
    WHERE receipt_id = 145294
    RETURNING receipt_id, receipt_date, banking_transaction_id
""")
updated = cur.fetchone()
if updated:
    print(f"   ✅ Updated: Receipt {updated[0]} | date={updated[1]} | banking_tx={updated[2]}")

conn.commit()

# Verify final counts
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'WCB' AND fiscal_year = 2012 AND gross_amount > 0
""")
count, total = cur.fetchone()

print(f"\n✅ Final 2012 WCB invoices: {count} = ${total:,.2f}")
print(f"   Excel target: 13 invoices = $4,593.00")

if count == 13 and abs(total - 4593.00) < 0.01:
    print("   🎉 DATABASE MATCHES EXCEL!")

conn.close()

#!/usr/bin/env python3
import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("Reference 18457712 in database:")
print("="*70)

cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description, banking_transaction_id
    FROM receipts
    WHERE vendor_name = 'WCB' AND source_reference = '18457712'
    ORDER BY receipt_date
""")

for row in cur.fetchall():
    receipt_id, date, amount, desc, banking_id = row
    desc_short = (desc[:50] if desc else "")
    print(f"  Receipt {receipt_id} | {date} | ${amount:,.2f} | Banking: {banking_id or 'None'}")
    print(f"    {desc_short}")

# Excel says it should be 2012-06-01, so delete the 2012-06-19 one
print("\n✅ Excel shows 2012-06-01, so the 2012-06-19 entry is a duplicate.")
print("   Deleting the 2012-06-19 entry...")

cur.execute("""
    DELETE FROM receipts
    WHERE vendor_name = 'WCB' 
    AND source_reference = '18457712'
    AND receipt_date = '2012-06-19'
    AND banking_transaction_id IS NULL
    RETURNING receipt_id
""")

deleted = cur.fetchone()
if deleted:
    print(f"   ✅ Deleted Receipt {deleted[0]}")
    conn.commit()
else:
    print("   ⚠️  No record deleted (might be banking-linked)")

conn.close()

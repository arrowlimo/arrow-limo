import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Find FAS GAS from 2012-11-14 (the split date)
print("🔍 ALL FAS GAS RECEIPTS from 2012-11-14:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id, description
    FROM receipts
    WHERE vendor_name ILIKE '%FAS%' AND receipt_date = '2012-11-14'
    ORDER BY gross_amount DESC
""")

rows = cur.fetchall()
if rows:
    for receipt_id, rec_date, vendor, amount, btx_id, desc in rows:
        print(f"  Receipt #{receipt_id}: {rec_date} | {vendor} | ${amount} | Banking TX: {btx_id}")
        print(f"    Desc: {desc[:80] if desc else 'N/A'}")
else:
    print("  NO RECEIPTS FOUND for 2012-11-14")

print("\n💰 ALL RECEIPTS linked to Banking TX #69544:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE banking_transaction_id = 69544
    ORDER BY gross_amount DESC
""")

rows = cur.fetchall()
if rows:
    for receipt_id, rec_date, vendor, amount, desc in rows:
        print(f"  Receipt #{receipt_id}: {rec_date} | {vendor} | ${amount}")
        print(f"    Desc: {desc[:80] if desc else 'N/A'}")
else:
    print("  NO RECEIPTS LINKED TO TX #69544")

print("\n🧮 TOTAL of all receipts linked to TX #69544:")
cur.execute("""
    SELECT SUM(gross_amount)
    FROM receipts
    WHERE banking_transaction_id = 69544
""")
total = cur.fetchone()[0]
print(f"  Total: ${total if total else 0}")

cur.close()
conn.close()

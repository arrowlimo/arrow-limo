import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Find FAS GAS close to 166.89
print("🔍 FAS GAS RECEIPTS near $166.89 (±$20):")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id, description
    FROM receipts
    WHERE vendor_name ILIKE '%FAS%' AND gross_amount BETWEEN 146.89 AND 186.89
    ORDER BY receipt_date DESC
""")

rows = cur.fetchall()
if rows:
    for receipt_id, rec_date, vendor, amount, btx_id, desc in rows:
        print(f"  Receipt #{receipt_id}: {rec_date} | {vendor} | ${amount} | Banking TX: {btx_id}")
else:
    print("  NO RECEIPTS FOUND between $146.89 and $186.89")

print("\n💰 BANKING TX #69544 (the $166.89 one):")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, vendor_extracted
    FROM banking_transactions
    WHERE transaction_id = 69544
""")

tx = cur.fetchone()
if tx:
    tx_id, tx_date, desc, debit, credit, vendor = tx
    amt = debit if debit else credit
    print(f"  TX #{tx_id}: {tx_date} | ${amt}")
    print(f"  Desc: {desc}")
    print(f"  Vendor: {vendor}")
    print(f"  Is this linked to ANY receipt?")
    
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount
        FROM receipts
        WHERE banking_transaction_id = 69544
    """)
    
    linked = cur.fetchone()
    if linked:
        rec_id, rec_vendor, rec_amt = linked
        print(f"    YES - Receipt #{rec_id} ({rec_vendor}, ${rec_amt})")
    else:
        print(f"    NO - NOT LINKED TO ANY RECEIPT")

cur.close()
conn.close()

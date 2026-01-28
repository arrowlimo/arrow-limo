import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Find all FAS GAS receipts
print("🔍 ALL FAS GAS RECEIPTS:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id
    FROM receipts
    WHERE vendor_name ILIKE '%FAS%'
    ORDER BY receipt_date DESC
    LIMIT 20
""")

rows = cur.fetchall()
if rows:
    for receipt_id, rec_date, vendor, amount, btx_id in rows:
        print(f"  Receipt #{receipt_id}: {rec_date} | {vendor} | ${amount} | Banking TX: {btx_id}")
else:
    print("  NO FAS GAS RECEIPTS FOUND")

print("\n🏦 ALL BANKING TRANSACTIONS for $166.89 (from ANY amount):")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, vendor_extracted, receipt_id
    FROM banking_transactions
    LEFT JOIN receipts r ON banking_transactions.transaction_id = r.banking_transaction_id
    WHERE (debit_amount = 166.89 OR credit_amount = 166.89)
    ORDER BY transaction_date DESC
""")

for tx_id, tx_date, desc, debit, credit, vendor, receipt_id in cur.fetchall():
    amt = debit if debit else credit
    linked = f"Receipt #{receipt_id}" if receipt_id else "NOT LINKED"
    print(f"  TX #{tx_id}: {tx_date} | ${amt} | {linked} | {desc[:60]}")

cur.close()
conn.close()

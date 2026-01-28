import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Find FAS GAS receipt for $166.89
print("🔍 RECEIPTS for $166.89 FAS GAS:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id, description
    FROM receipts
    WHERE gross_amount = 166.89 AND vendor_name ILIKE '%FAS%'
    ORDER BY receipt_date DESC
""")

for receipt_id, rec_date, vendor, amount, btx_id, desc in cur.fetchall():
    print(f"  Receipt #{receipt_id}: {rec_date} | {vendor} | ${amount} | Banking TX: {btx_id}")
    print(f"    Desc: {desc[:80]}")

print("\n🏦 BANKING TRANSACTIONS for $166.89:")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, vendor_extracted
    FROM banking_transactions
    WHERE (debit_amount = 166.89 OR credit_amount = 166.89)
    ORDER BY transaction_date DESC
""")

for tx_id, tx_date, desc, debit, credit, vendor in cur.fetchall():
    amt = debit if debit else credit
    print(f"  TX #{tx_id}: {tx_date} | ${amt} | {vendor}")
    print(f"    Desc: {desc[:80]}")

cur.close()
conn.close()

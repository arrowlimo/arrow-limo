"""
Show date and banking description details for the two large CHEQUE error receipts.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Get the two large CHEQUE error receipts with full banking details
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.banking_transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount,
        bt.balance
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('CHEQUE 955.46', 'CHEQUE WO -120.00')
    ORDER BY r.receipt_date DESC
""")

print("=== LARGE CHEQUE ERROR RECEIPTS - VERIFICATION DETAILS ===\n")

for row in cur.fetchall():
    receipt_id, receipt_date, vendor_name, gross_amount, btid, bt_date, bt_desc, debit, credit, balance = row
    print(f"Receipt ID: {receipt_id}")
    print(f"Receipt Date: {receipt_date}")
    print(f"Vendor Name: {vendor_name}")
    print(f"Gross Amount: ${gross_amount:,.2f}")
    print()
    print(f"Banking Transaction ID: {btid}")
    if bt_date:
        print(f"Bank TX Date: {bt_date}")
        print(f"Bank Description: {bt_desc}")
        print(f"Debit: ${debit:,.2f}" if debit else "Debit: None")
        print(f"Credit: ${credit:,.2f}" if credit else "Credit: None")
        print(f"Balance After: ${balance:,.2f}" if balance else "Balance: None")
    print()
    print("-" * 80)
    print()

cur.close()
conn.close()

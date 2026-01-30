"""
Check unmatched UNKNOWN PAYEE receipts (no payee in cheque_register).
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

# Get unmatched UNKNOWN PAYEE receipts
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.banking_transaction_id,
        bt.description as bank_description,
        cr.cheque_number,
        cr.payee
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    LEFT JOIN cheque_register cr ON r.banking_transaction_id = cr.banking_transaction_id
    WHERE r.vendor_name = 'UNKNOWN PAYEE'
    AND cr.payee IS NULL
    ORDER BY r.receipt_date, r.receipt_id
    LIMIT 30
""")

print("=== UNMATCHED UNKNOWN PAYEE (first 30) ===\n")
for receipt_id, receipt_date, gross_amount, btid, bank_desc, cheque_num, payee in cur.fetchall():
    print(f"ID {receipt_id:6d}  {receipt_date}  ${gross_amount:10.2f}  BTID {btid}")
    print(f"  Bank: {bank_desc}")
    print(f"  Cheque: {cheque_num}, Payee: {payee}")
    print()

cur.close()
conn.close()

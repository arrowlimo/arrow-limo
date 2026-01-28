"""
Extract cheque number → payee mappings from banking_transactions descriptions.
Then update unmatched UNKNOWN PAYEE receipts.
Apply overrides: TREDD → IFS, WELCOME WAGON → ADVERTISING
"""
import psycopg2
import os
import re

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# First, get all unmatched receipts with their cheque numbers from banking descriptions
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.banking_transaction_id,
        bt.description as bank_description
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'UNKNOWN PAYEE'
    AND r.banking_transaction_id IS NOT NULL
    ORDER BY r.receipt_date, r.receipt_id
""")

unmatched = cur.fetchall()
print(f"Total unmatched receipts: {len(unmatched)}\n")

# Extract cheque numbers and create a reverse lookup
cheque_to_receipt = {}
for receipt_id, receipt_date, gross_amount, btid, bank_desc in unmatched:
    # Extract cheque number from description (CHQ #243, CHQ 1, chq 23, Cheque #243, etc.)
    match = re.search(r'(?:CHQ|Cheque|chq)\s*#?(\d+)', bank_desc, re.IGNORECASE)
    if match:
        cheque_num = match.group(1)
        cheque_to_receipt[cheque_num] = (receipt_id, bank_desc)

print(f"Unique cheque numbers found: {len(cheque_to_receipt)}")
print("\nCheque numbers to resolve:")
for chq in sorted(cheque_to_receipt.keys(), key=int):
    receipt_id, desc = cheque_to_receipt[chq]
    print(f"  CHQ {chq}: Receipt {receipt_id} ({desc})")

cur.close()
conn.close()

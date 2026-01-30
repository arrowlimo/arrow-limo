"""
Update UNKNOWN PAYEE receipts with vendor names from cheque_register.
Matches receipts to cheque_register via banking_transaction_id.
"""
import psycopg2
import os
import sys

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Get all UNKNOWN PAYEE receipts with their banking_transaction_id and cheque info
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.banking_transaction_id,
        bt.description as bank_description,
        cr.payee,
        cr.cheque_number,
        cr.memo
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    LEFT JOIN cheque_register cr ON r.banking_transaction_id = cr.banking_transaction_id
    WHERE r.vendor_name = 'UNKNOWN PAYEE'
    ORDER BY r.receipt_date, r.receipt_id
""")

results = cur.fetchall()
print(f"Total UNKNOWN PAYEE receipts: {len(results)}\n")

# Count matches
matched = 0
unmatched = 0
updates_by_payee = {}

for receipt_id, receipt_date, amount, btid, bank_desc, payee, cheque_num, memo in results:
    if payee:
        matched += 1
        updates_by_payee[payee] = updates_by_payee.get(payee, 0) + 1
    else:
        unmatched += 1

print(f"Matched to cheque_register: {matched}")
print(f"Unmatched (no cheque payee): {unmatched}\n")

if matched > 0:
    print("=== UPDATE SUMMARY BY PAYEE ===")
    for payee in sorted(updates_by_payee.keys(), key=lambda x: -updates_by_payee[x]):
        count = updates_by_payee[payee]
        print(f"  {payee}: {count} receipts")

    # Ask for confirmation before updating
    print(f"\nReady to update {matched} receipts to their matched payee names.")
    response = input("Execute update? (yes/no): ").strip().lower()
    
    if response == 'yes':
        update_count = 0
        for receipt_id, receipt_date, amount, btid, bank_desc, payee, cheque_num, memo in results:
            if payee:
                cur.execute("""
                    UPDATE receipts
                    SET vendor_name = %s
                    WHERE receipt_id = %s
                """, (payee, receipt_id))
                update_count += 1
        
        conn.commit()
        print(f"\n✅ Updated {update_count} receipts")
    else:
        print("Cancelled.")
else:
    print("No matched payees found in cheque_register.")

cur.close()
conn.close()

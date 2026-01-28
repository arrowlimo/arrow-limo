"""
Match unmatched UNKNOWN PAYEE receipts to cheque payees from cheque_register.
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

# Hardcoded overrides
overrides = {
    'TREDD': 'IFS',
    'WELCOME WAGON': 'ADVERTISING',
}

# Get all cheque records from cheque_register with payee names
cur.execute("""
    SELECT cheque_number, payee
    FROM cheque_register
    WHERE payee IS NOT NULL
    ORDER BY cheque_number
""")

cheque_payees = {}
for chq_num, payee in cur.fetchall():
    if chq_num and payee:
        cheque_payees[str(chq_num)] = payee
        # Also add numeric version
        try:
            cheque_payees[int(chq_num)] = payee
        except:
            pass

print(f"Loaded {len(set(cheque_payees.values()))} unique cheque payees\n")

# Get unmatched UNKNOWN PAYEE receipts with their banking descriptions
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
print(f"Total unmatched UNKNOWN PAYEE receipts: {len(unmatched)}\n")

# Try to match cheque numbers to payees
updates_to_apply = []
matched_count = 0
unmatched_count = 0

for receipt_id, receipt_date, gross_amount, btid, bank_desc in unmatched:
    payee = None
    cheque_num = None
    
    # Extract cheque number from banking description
    match = re.search(r'(?:CHQ|Cheque|chq)\s*#?(\d+)', bank_desc, re.IGNORECASE)
    if match:
        cheque_num = match.group(1)
        # Try to find payee in cheque_register
        if cheque_num in cheque_payees:
            payee = cheque_payees[cheque_num]
            matched_count += 1
        else:
            # Try with leading zeros stripped
            try:
                numeric = int(cheque_num)
                if numeric in cheque_payees:
                    payee = cheque_payees[numeric]
                    matched_count += 1
            except:
                pass
    
    # If still no payee, use generic
    if not payee:
        payee = 'CHEQUE (Payee unknown)'
        unmatched_count += 1
    
    # Apply overrides
    if payee in overrides:
        original = payee
        payee = overrides[payee]
        print(f"  Override: {original} → {payee}")
    
    updates_to_apply.append((receipt_id, payee, cheque_num))

print(f"\nMatched: {matched_count}, Unmatched: {unmatched_count}\n")

# Show updates by payee
payee_counts = {}
for receipt_id, payee, chq_num in updates_to_apply:
    payee_counts[payee] = payee_counts.get(payee, 0) + 1

print("=== UPDATE SUMMARY ===")
for payee in sorted(payee_counts.keys(), key=lambda x: -payee_counts[x]):
    count = payee_counts[payee]
    print(f"  {payee}: {count} receipts")

response = input("\nExecute updates? (yes/no): ").strip().lower()

if response == 'yes':
    update_count = 0
    for receipt_id, payee, chq_num in updates_to_apply:
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

cur.close()
conn.close()

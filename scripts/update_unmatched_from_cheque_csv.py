"""
Create cheque → payee mapping from the cheque sheet in the attachment.
Updates unmatched UNKNOWN PAYEE receipts.
Apply overrides: TREDD → IFS, WELCOME WAGON → ADVERTISING
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

# Hardcoded overrides from user
overrides = {
    'TREDD': 'IFS',
    'WELCOME WAGON': 'ADVERTISING',
}

# Read the cheque register CSV with payee names
cheque_payees = {}
try:
    with open('l:\\limo\\reports\\cheque_register_20251210_175553.csv', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[1:]:  # Skip header
            parts = line.strip().split(',')
            if len(parts) >= 2:
                cheque_num = parts[1].strip('"')  # cheque_number column
                issuing_name = parts[2].strip('"')  # issuing_name column
                if cheque_num and issuing_name and issuing_name != '0000':
                    # Normalize the cheque number (remove leading zeros for matching)
                    cheque_payees[cheque_num] = issuing_name
except:
    print("Warning: Could not read cheque_register CSV")

print(f"Loaded {len(cheque_payees)} cheque → payee mappings from CSV\n")

# Get unmatched UNKNOWN PAYEE receipts with their cheque numbers
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

# Extract payees and prepare updates
updates_to_apply = []
for receipt_id, receipt_date, gross_amount, btid, bank_desc in unmatched:
    payee = None
    
    # Try to find in CSV mapping
    for chq_num, chq_payee in cheque_payees.items():
        if str(chq_num) in bank_desc or bank_desc in str(chq_num):
            payee = chq_payee
            break
    
    # If not found, use generic "CHEQUE" name
    if not payee:
        payee = 'CHEQUE (No payee on record)'
    
    # Apply overrides
    if payee in overrides:
        payee = overrides[payee]
    
    updates_to_apply.append((receipt_id, payee))

print(f"Ready to update {len(updates_to_apply)} receipts with payee names\n")

# Show sample updates
print("Sample updates:")
for receipt_id, payee in updates_to_apply[:10]:
    print(f"  Receipt {receipt_id}: → {payee}")

response = input("\nExecute updates? (yes/no): ").strip().lower()

if response == 'yes':
    update_count = 0
    for receipt_id, payee in updates_to_apply:
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

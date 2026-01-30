"""
Move/Delete banking import vendor expenses from receipts table
These are already tracked in banking_transactions, so we'll remove them from receipts
to avoid double-counting and confusion
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

# Known vendor patterns
known_vendors = [
    'WCB', 'WORKERS COMPENSATION', 'FAS GAS', 'SHELL', 'PETRO', 'ESSO',
    'TELUS', 'SHAW', 'ENMAX', 'LEASE', 'INSURANCE', 'CRA', 'REVENUE',
    'ATB', 'CIBC', 'SCOTIA', 'MASTERCARD', 'VISA', 'AMEX',
    '106.7', 'KOOL', 'RADIO', 'ADVERTISING', 'CO-OP', 'DAIRY QUEEN',
    'TIM HORTONS', 'NOFRILLS', 'ROGERS', 'SERVICE CHARGE', 'CASH WITHDRAWAL',
    'OVERDRAFT', 'FIBRENEW', 'SUPER CLEAN', 'PETROLEUM', 'CREDIT MEMO'
]

print("=== Moving/Deleting Banking Import Vendor Expenses ===\n")

# Build vendor pattern for SQL
vendor_conditions = []
for vendor in known_vendors:
    vendor_conditions.append(f"vendor_name ILIKE '%{vendor}%'")

vendor_pattern = ' OR '.join(vendor_conditions)

# Find all vendor payment receipts from banking
cur.execute(f"""
    SELECT receipt_id, vendor_name, source_reference, receipt_date, 
           gross_amount, description, banking_transaction_id
    FROM receipts
    WHERE (created_from_banking = true OR source_reference = 'BANKING_IMPORT')
      AND ({vendor_pattern} OR gross_amount < 0)
    ORDER BY receipt_date
""")

vendor_receipts = cur.fetchall()
print(f"Total vendor payment receipts to process: {len(vendor_receipts)}\n")

# Create a backup log
backup_log = []
total_amount = 0

print("Sample of records to be deleted (first 20):\n")
for i, row in enumerate(vendor_receipts[:20]):
    receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id = row
    amt_str = f"${amount:,.2f}" if amount is not None else "$0.00"
    print(f"  {receipt_id}: {vendor_name or '(no vendor)'}, {amt_str} on {date}")
    if i < 5 and desc:
        print(f"      {desc[:80]}")

print(f"\n... and {len(vendor_receipts) - 20} more\n")

# Confirm
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"This will DELETE {len(vendor_receipts)} receipts that are:")
print("  - Vendor expenses (SHELL, TELUS, WCB, etc.)")
print("  - Already in banking_transactions table")
print("  - Incorrectly showing as revenue in receipts table")
print()
print("These transactions will remain in banking_transactions (the authoritative source)")
print("=" * 80)

response = input("\nProceed with deletion? (yes/no): ").strip().lower()

if response != 'yes':
    print("\n❌ Cancelled. No changes made.")
    conn.close()
    exit()

print("\n🗑️  Deleting receipts...\n")

deleted_count = 0
for row in vendor_receipts:
    receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id = row
    
    # Save to backup log
    backup_log.append({
        'receipt_id': receipt_id,
        'vendor_name': vendor_name,
        'source_ref': source_ref,
        'date': str(date),
        'amount': float(amount) if amount else 0.0,
        'description': desc,
        'banking_tx_id': bank_tx_id
    })
    
    # Delete banking links first
    cur.execute("DELETE FROM banking_receipt_matching_ledger WHERE receipt_id = %s", (receipt_id,))
    
    # Remove receipt_id reference from banking_transactions
    cur.execute("UPDATE banking_transactions SET receipt_id = NULL WHERE receipt_id = %s", (receipt_id,))
    
    # Delete the receipt
    cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
    
    deleted_count += 1
    total_amount += (amount or 0)
    
    if deleted_count % 100 == 0:
        print(f"  Deleted {deleted_count} receipts...")

print(f"\n✅ Deleted {deleted_count} vendor expense receipts")
print(f"Total amount removed from receipts: ${total_amount:,.2f}")

# Save backup log
import json
backup_file = 'reports/DELETED_VENDOR_BANKING_RECEIPTS_BACKUP.json'
with open(backup_file, 'w') as f:
    json.dump(backup_log, f, indent=2)

print(f"\n📄 Backup saved to: {backup_file}")

conn.commit()
cur.close()
conn.close()

print("\n✅ Complete! Banking import vendor expenses removed from receipts table.")
print("These transactions remain in banking_transactions as the authoritative record.")

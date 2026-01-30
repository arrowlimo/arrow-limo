"""
Verify all BANKING_IMPORT records marked as revenue (receipts table)
Identify any that might be payments TO vendors instead of FROM customers
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("=== Verifying BANKING_IMPORT Revenue Records ===\n")

# Find all banking imports in receipts table (revenue side)
cur.execute("""
    SELECT receipt_id, vendor_name, source_reference, receipt_date, 
           gross_amount, description, banking_transaction_id
    FROM receipts
    WHERE created_from_banking = true 
       OR source_reference = 'BANKING_IMPORT'
       OR source_file LIKE '%BANKING%'
    ORDER BY receipt_date, receipt_id
""")

all_banking_receipts = cur.fetchall()
print(f"Total banking import receipts: {len(all_banking_receipts)}\n")

# Categorize them
vendor_payments = []  # These are likely WRONG - payments TO vendors
customer_payments = []  # These are correct - payments FROM customers
unclear = []

# Known vendors (you pay these)
known_vendors = [
    'WCB', 'WORKERS COMPENSATION', 'FAS GAS', 'SHELL', 'PETRO', 'ESSO',
    'TELUS', 'SHAW', 'ENMAX', 'LEASE', 'INSURANCE', 'CRA', 'REVENUE',
    'ATB', 'CIBC', 'SCOTIA', 'MASTERCARD', 'VISA', 'AMEX',
    '106.7', 'KOOL', 'RADIO', 'ADVERTISING'
]

for row in all_banking_receipts:
    receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id = row
    
    # Skip if amount is None
    if amount is None:
        unclear.append(row)
        continue
    
    if vendor_name:
        # Check if this is a known vendor
        is_vendor = any(v.upper() in vendor_name.upper() for v in known_vendors)
        
        if is_vendor:
            vendor_payments.append(row)
        else:
            # Could be a customer name or unclear
            if amount < 0:  # Negative amounts in receipts are definitely wrong
                vendor_payments.append(row)
            else:
                unclear.append(row)
    else:
        # No vendor name - likely customer payment or unclear
        if desc and any(v.upper() in (desc or '').upper() for v in known_vendors):
            vendor_payments.append(row)
        else:
            customer_payments.append(row)

print("=" * 80)
print("🚨 LIKELY INCORRECT - Payments TO Vendors (should not be in receipts)")
print("=" * 80)
if vendor_payments:
    print(f"\nFound {len(vendor_payments)} potential issues:\n")
    total_incorrect = 0
    for row in vendor_payments:
        receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id = row
        print(f"Receipt {receipt_id}: {vendor_name or '(no vendor)'}")
        print(f"  Date: {date}, Amount: ${amount:,.2f}")
        print(f"  Banking TX: {bank_tx_id}")
        if desc:
            desc_preview = desc[:100] + '...' if len(desc) > 100 else desc
            print(f"  Description: {desc_preview}")
        print()
        total_incorrect += amount
    
    print(f"Total amount in incorrect receipts: ${total_incorrect:,.2f}")
else:
    print("✅ No obvious vendor payments found in receipts!")

print("\n" + "=" * 80)
print("✅ LIKELY CORRECT - Payments FROM Customers")
print("=" * 80)
print(f"Found {len(customer_payments)} customer payment receipts")
if customer_payments:
    total_correct = sum(row[4] for row in customer_payments)
    print(f"Total amount: ${total_correct:,.2f}")
    print(f"\nSample (first 5):")
    for row in customer_payments[:5]:
        receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id = row
        print(f"  Receipt {receipt_id}: ${amount:,.2f} on {date} - {vendor_name or '(no vendor)'}")

print("\n" + "=" * 80)
print("⚠️  UNCLEAR - Need Manual Review")
print("=" * 80)
if unclear:
    print(f"\nFound {len(unclear)} unclear records (showing first 10):\n")
    for row in unclear[:10]:  # Show only first 10
        receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id = row
        amt_str = f"${amount:,.2f}" if amount is not None else "$0.00"
        print(f"Receipt {receipt_id}: {vendor_name or '(no vendor)'}")
        print(f"  Date: {date}, Amount: {amt_str}")
        if desc:
            desc_preview = desc[:80] + '...' if len(desc) > 80 else desc
            print(f"  Description: {desc_preview}")
        print()
    if len(unclear) > 10:
        print(f"... and {len(unclear) - 10} more unclear records")
else:
    print("None")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total banking import receipts: {len(all_banking_receipts)}")
print(f"  🚨 Likely incorrect (vendor payments): {len(vendor_payments)}")
print(f"  ✅ Likely correct (customer payments): {len(customer_payments)}")
print(f"  ⚠️  Unclear (need review): {len(unclear)}")

cur.close()
conn.close()

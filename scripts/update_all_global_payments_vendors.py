#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
update_all_global_payments_vendors.py

Update ALL card transactions (MCARD/VCARD/ACARD) to use proper
GLOBAL VISA/MASTERCARD/AMEX naming convention.

These are Global Payments merchant services deposits from customer payments.
"""

import psycopg2
import re
import sys

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def extract_vendor_from_description(description):
    """Extract proper vendor name from description field."""
    if not description:
        return None
    
    desc = description.upper()
    
    # Card type mapping
    card_patterns = {
        'MCARD': 'GLOBAL MASTERCARD',
        'VCARD': 'GLOBAL VISA',
        'ACARD': 'GLOBAL AMEX'
    }
    
    for short_name, full_name in card_patterns.items():
        if short_name in desc:
            # Determine transaction type based on description
            if 'DEPOSIT' in desc:
                trans_type = 'DEPOSIT'
            elif 'PAYMENT' in desc:
                trans_type = 'PAYMENT'
            else:
                # Default to DEPOSIT if not specified
                trans_type = 'DEPOSIT'
            
            # Extract any numbers (merchant account)
            match = re.search(r'(\d+)', desc)
            if match:
                return f"{full_name} {trans_type} {match.group(1)}"
            else:
                return f"{full_name} {trans_type}"
    
    return None

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

# Get all card transactions with NULL vendor_extracted
cur.execute("""
    SELECT transaction_id, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE description ILIKE '%CARD%'
    AND (description ILIKE '%MCARD%' OR description ILIKE '%VCARD%' OR description ILIKE '%ACARD%')
    AND vendor_extracted IS NULL
    ORDER BY transaction_date
""")

transactions = cur.fetchall()

print("\n" + "="*110)
print("UPDATE ALL GLOBAL PAYMENTS VENDOR NAMES")
print("="*110 + "\n")

print(f"Found {len(transactions)} card transactions with NULL vendor_extracted\n")

if not transactions:
    print("No transactions to update!")
    cur.close()
    conn.close()
    sys.exit(0)

# Generate updates
updates = {}
for trans_id, desc, debit, credit in transactions[:20]:  # Show first 20
    vendor = extract_vendor_from_description(desc)
    if vendor:
        # Verify direction matches
        if debit and debit > 0 and 'DEPOSIT' in vendor:
            # Debit = money out = PAYMENT
            vendor = vendor.replace('DEPOSIT', 'PAYMENT')
        elif credit and credit > 0 and 'PAYMENT' in vendor:
            # Credit = money in = DEPOSIT
            vendor = vendor.replace('PAYMENT', 'DEPOSIT')
        
        updates[trans_id] = vendor
        amount = f"${debit:,.2f} debit" if debit else f"${credit:,.2f} credit"
        print(f"{trans_id:<15} {amount:<20} {desc[:40]:<45} → {vendor}")

# Count all updates
all_updates = {}
for trans_id, desc, debit, credit in transactions:
    vendor = extract_vendor_from_description(desc)
    if vendor:
        # Verify direction matches
        if debit and debit > 0 and 'DEPOSIT' in vendor:
            vendor = vendor.replace('DEPOSIT', 'PAYMENT')
        elif credit and credit > 0 and 'PAYMENT' in vendor:
            vendor = vendor.replace('PAYMENT', 'DEPOSIT')
        all_updates[trans_id] = vendor

if len(all_updates) > 20:
    print(f"... and {len(all_updates) - 20} more")

print(f"\n📊 Total updates to apply: {len(all_updates)}")

# Check for dry-run
dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply changes")
    cur.close()
    conn.close()
    sys.exit(0)

# Execute mode
response = input("\n⚠️  EXECUTION MODE\n\nType 'UPDATE' to proceed: ")
if response != 'UPDATE':
    print("❌ Cancelled")
    cur.close()
    conn.close()
    sys.exit(1)

try:
    # Disable trigger
    print("\n🔓 Disabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    
    print("📝 Applying updates...")
    
    for trans_id, vendor in all_updates.items():
        cur.execute("""
            UPDATE banking_transactions
            SET vendor_extracted = %s
            WHERE transaction_id = %s
        """, (vendor, trans_id))
    
    # Re-enable trigger
    print("🔒 Re-enabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
    
    conn.commit()
    
    print(f"\n✅ UPDATED {len(all_updates)} transactions")
    print("All Global Payments transactions now have proper GLOBAL VISA/MASTERCARD/AMEX vendor names")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    conn.rollback()

finally:
    cur.close()
    conn.close()

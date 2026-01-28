#!/usr/bin/env python3
"""
Revert Global Payments vendor names to short form:
- GLOBAL VISA DEPOSIT → VCARD DEPOSIT
- GLOBAL MASTERCARD DEPOSIT → MCARD DEPOSIT  
- GLOBAL AMEX DEPOSIT → ACARD DEPOSIT
- GLOBAL VISA PAYMENT → VCARD PAYMENT
- GLOBAL MASTERCARD PAYMENT → MCARD PAYMENT
- GLOBAL AMEX PAYMENT → ACARD PAYMENT

Note: DCARD DEPOSIT is for debit cards (NOT Global Payments), keep separate.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

print("=" * 80)
print("REVERTING GLOBAL PAYMENTS TO SHORT FORM VENDOR NAMES")
print("=" * 80)

# Mapping of long form to short form
VENDOR_MAPPINGS = {
    'GLOBAL VISA DEPOSIT': 'VCARD DEPOSIT',
    'GLOBAL VISA DEPOSIT 00339': 'VCARD DEPOSIT',
    'GLOBAL MASTERCARD DEPOSIT': 'MCARD DEPOSIT',
    'GLOBAL MASTERCARD DEPOSIT 00339': 'MCARD DEPOSIT',
    'GLOBAL AMEX DEPOSIT': 'ACARD DEPOSIT',
    'GLOBAL AMEX DEPOSIT 7839': 'ACARD DEPOSIT',
    'GLOBAL VISA PAYMENT': 'VCARD PAYMENT',
    'GLOBAL VISA PAYMENT 1': 'VCARD PAYMENT',
    'GLOBAL VISA PAYMENT 2': 'VCARD PAYMENT',
    'GLOBAL VISA PAYMENT 00339': 'VCARD PAYMENT',
    'GLOBAL MASTERCARD PAYMENT': 'MCARD PAYMENT',
    'GLOBAL MASTERCARD PAYMENT 00339': 'MCARD PAYMENT',
    'GLOBAL MASTERCARD PAYMENT 097384700019': 'MCARD PAYMENT',
    'GLOBAL AMEX PAYMENT': 'ACARD PAYMENT',
}

cur = conn.cursor()

# Check banking_transactions
print("\n1. BANKING TRANSACTIONS")
print("-" * 80)

for old_name, new_name in VENDOR_MAPPINGS.items():
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions 
        WHERE vendor_extracted = %s
    """, (old_name,))
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"\n'{old_name}' → '{new_name}' ({count} transactions)")

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE vendor_extracted IN %s
""", (tuple(VENDOR_MAPPINGS.keys()),))
total_banking = cur.fetchone()[0]

print(f"\nTotal banking transactions to update: {total_banking}")

# Check receipts
print("\n\n2. RECEIPTS")
print("-" * 80)

for old_name, new_name in VENDOR_MAPPINGS.items():
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts 
        WHERE vendor_name = %s
    """, (old_name,))
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"\n'{old_name}' → '{new_name}' ({count} receipts)")

# Get total receipts count
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE vendor_name IN %s
""", (tuple(VENDOR_MAPPINGS.keys()),))
total_receipts = cur.fetchone()[0]

print(f"\nTotal receipts to update: {total_receipts}")

# Confirmation
print("\n" + "=" * 80)
print(f"Ready to update:")
print(f"  Banking transactions: {total_banking}")
print(f"  Receipts: {total_receipts}")
print("=" * 80)

confirm = input("\nProceed with update? (yes/no): ").strip().lower()

if confirm == 'yes':
    print("\n🔓 Disabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    
    print("📝 Updating banking_transactions...")
    banking_updated = 0
    for old_name, new_name in VENDOR_MAPPINGS.items():
        cur.execute("""
            UPDATE banking_transactions 
            SET vendor_extracted = %s 
            WHERE vendor_extracted = %s
        """, (new_name, old_name))
        banking_updated += cur.rowcount
    
    print(f"   Updated {banking_updated} banking transactions")
    
    print("\n📝 Updating receipts...")
    receipts_updated = 0
    for old_name, new_name in VENDOR_MAPPINGS.items():
        cur.execute("""
            UPDATE receipts 
            SET vendor_name = %s 
            WHERE vendor_name = %s
        """, (new_name, old_name))
        receipts_updated += cur.rowcount
    
    print(f"   Updated {receipts_updated} receipts")
    
    print("\n🔒 Re-enabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
    
    print("\n💾 Committing changes...")
    conn.commit()
    
    print("\n✅ UPDATE COMPLETE")
    print(f"   Banking transactions: {banking_updated}")
    print(f"   Receipts: {receipts_updated}")
    
    # Verify
    print("\n\nVerification:")
    cur.execute("""
        SELECT vendor_extracted, COUNT(*) 
        FROM banking_transactions 
        WHERE vendor_extracted LIKE '%CARD %'
        GROUP BY vendor_extracted 
        ORDER BY COUNT(*) DESC
    """)
    print("\nBanking card vendors:")
    for vendor, count in cur.fetchall():
        print(f"  {vendor}: {count}")
    
else:
    print("\n❌ Update cancelled")

cur.close()
conn.close()

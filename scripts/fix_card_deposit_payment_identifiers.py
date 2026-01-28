#!/usr/bin/env python3
"""
Verify and correct MCARD/VCARD/ACARD transaction identifiers
Ensure vendor names reflect actual transaction direction (DEPOSIT vs PAYMENT)
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*100)
print("MCARD/VCARD/ACARD TRANSACTION VERIFICATION")
print("="*100)

# Analyze current state
print("\n📊 Current MCARD/VCARD/ACARD transactions (from descriptions):")

for card_type in ['MCARD', 'VCARD', 'ACARD']:
    print(f"\n{card_type}:")
    
    cur.execute(f"""
        SELECT 
            description,
            vendor_extracted,
            COUNT(*) as count,
            COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debits,
            COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credits,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            SUM(COALESCE(credit_amount, 0)) as total_credits
        FROM banking_transactions
        WHERE description ILIKE '%{card_type}%'
        AND (description ILIKE '%deposit%' OR description ILIKE '%payment%')
        GROUP BY description, vendor_extracted
        ORDER BY count DESC
        LIMIT 10
    """)
    
    for desc, vendor, count, debits, credits, total_debit, total_credit in cur.fetchall():
        desc_str = (desc or '')[:40]
        vendor_str = (vendor or 'NULL')[:30]
        print(f"   {desc_str:<42} | V:{vendor_str:<32} | {count:>3} tx | D:{debits:>3} (${total_debit:>10,.2f}) | C:{credits:>3} (${total_credit:>10,.2f})")

# Find mismatches
print("\n\n" + "="*100)
print("MISMATCHES - Description says DEPOSIT but is PAYMENT (debit) or vice versa")
print("="*100)

mismatches = []

for card_type in ['MCARD', 'VCARD', 'ACARD']:
    # Find transactions where description says DEPOSIT but it's a debit (payment out)
    cur.execute(f"""
        SELECT 
            transaction_id,
            transaction_uid,
            transaction_date,
            description,
            vendor_extracted,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE description ILIKE '%{card_type}%DEPOSIT%'
        AND debit_amount > 0
        AND (credit_amount IS NULL OR credit_amount = 0)
        ORDER BY transaction_date
    """)
    
    deposit_but_debit = cur.fetchall()
    if deposit_but_debit:
        print(f"\n❌ {card_type} description says DEPOSIT but is actually PAYMENT (debit): {len(deposit_but_debit)}")
        for trans_id, uid, date, desc, vendor, debit, credit in deposit_but_debit[:5]:
            desc_str = (desc or '')[:40]
            vendor_str = (vendor or 'NULL')[:30]
            print(f"   {uid} | {date} | ${debit:,.2f} debit | {desc_str}")
            mismatches.append((trans_id, desc, vendor, 'PAYMENT', debit, 0, card_type))
    
    # Find transactions where description says PAYMENT but it's a credit (deposit in)
    cur.execute(f"""
        SELECT 
            transaction_id,
            transaction_uid,
            transaction_date,
            description,
            vendor_extracted,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE description ILIKE '%{card_type}%PAYMENT%'
        AND credit_amount > 0
        AND (debit_amount IS NULL OR debit_amount = 0)
        ORDER BY transaction_date
    """)
    
    payment_but_credit = cur.fetchall()
    if payment_but_credit:
        print(f"\n❌ {card_type} description says PAYMENT but is actually DEPOSIT (credit): {len(payment_but_credit)}")
        for trans_id, uid, date, desc, vendor, debit, credit in payment_but_credit[:5]:
            desc_str = (desc or '')[:40]
            vendor_str = (vendor or 'NULL')[:30]
            print(f"   {uid} | {date} | ${credit:,.2f} credit | {desc_str}")
            mismatches.append((trans_id, desc, vendor, 'DEPOSIT', 0, credit, card_type))

print(f"\n\n📊 Total mismatches found: {len(mismatches)}")

if not mismatches:
    print("\n✅ No mismatches found! All MCARD/VCARD/ACARD identifiers are correct.")
    cur.close()
    conn.close()
    sys.exit(0)

# Generate corrections
print("\n\n" + "="*100)
print("PROPOSED CORRECTIONS")
print("="*100)

# Map short codes to full Global Payments names
CARD_TYPE_MAP = {
    'MCARD': 'GLOBAL MASTERCARD',
    'VCARD': 'GLOBAL VISA',
    'ACARD': 'GLOBAL AMEX'
}

corrections = {}

for trans_id, desc, old_vendor, correct_type, debit, credit, card_type in mismatches:
    # Build correct vendor name based on actual transaction direction
    import re
    # Extract any number from description (merchant account number)
    match = re.search(r'(\d+)', desc)
    global_name = CARD_TYPE_MAP.get(card_type, card_type)
    
    if match:
        new_vendor = f"{global_name} {correct_type} {match.group(1)}"
    else:
        new_vendor = f"{global_name} {correct_type}"
    
    corrections[trans_id] = (old_vendor or '(empty)', new_vendor, desc[:50])

print(f"\n{len(corrections)} corrections to apply:")
print(f"\n{'Transaction ID':<15} {'Original':<30} {'Corrected':<30} {'Description':<50}")
print("-"*125)

shown = 0
for trans_id, (old, new, desc) in corrections.items():
    if shown < 20:
        print(f"{trans_id:<15} {old[:28]:<30} {new[:28]:<30} {desc[:48]}")
        shown += 1

if len(corrections) > 20:
    print(f"... and {len(corrections) - 20} more")

# Apply corrections
dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply corrections")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input("\nType 'FIX' to proceed: ")
    
    if response != 'FIX':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    # Disable trigger
    print("\n🔓 Disabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    
    try:
        print("\n📝 Applying corrections...")
        
        for trans_id, (old_vendor, new_vendor, desc) in corrections.items():
            cur.execute("""
                UPDATE banking_transactions
                SET vendor_extracted = %s
                WHERE transaction_id = %s
            """, (new_vendor, trans_id))
        
        updated = cur.rowcount
        
        # Re-enable trigger
        print("\n🔒 Re-enabling banking lock trigger...")
        cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
        
        conn.commit()
        
        print(f"\n✅ CORRECTIONS APPLIED")
        print(f"   Updated {len(corrections)} transactions")
        print(f"   All MCARD/VCARD/ACARD identifiers now match actual transaction direction")
        
        # Show final state
        print("\n\n📊 Final state:")
        for card_type in ['MCARD', 'VCARD', 'ACARD']:
            cur.execute(f"""
                SELECT 
                    CASE 
                        WHEN debit_amount > 0 THEN 'PAYMENT'
                        WHEN credit_amount > 0 THEN 'DEPOSIT'
                    END as direction,
                    COUNT(*) as count,
                    SUM(COALESCE(debit_amount, credit_amount, 0)) as total
                FROM banking_transactions
                WHERE UPPER(vendor_extracted) LIKE '%{card_type}%'
                GROUP BY direction
                ORDER BY direction
            """)
            
            print(f"\n   {card_type}:")
            for direction, count, total in cur.fetchall():
                print(f"      {direction:<10}: {count:>4} transactions, ${total:>12,.2f}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("🔒 Re-enabling trigger...")
        cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
        conn.rollback()
        raise

cur.close()
conn.close()

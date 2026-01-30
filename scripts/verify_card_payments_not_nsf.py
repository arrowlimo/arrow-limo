#!/usr/bin/env python3
"""
Verify VCARD/MCARD/ACARD PAYMENT transactions are NOT NSF charges.
Check descriptions to ensure they're legitimate Global Payments chargebacks/reversals.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

print("=" * 80)
print("VERIFYING CARD PAYMENT TRANSACTIONS ARE NOT NSF CHARGES")
print("=" * 80)

cur = conn.cursor()

# Check all CARD PAYMENT transactions
cur.execute("""
    SELECT 
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount,
        category
    FROM banking_transactions
    WHERE vendor_extracted IN ('VCARD PAYMENT', 'MCARD PAYMENT', 'ACARD PAYMENT')
    ORDER BY transaction_date DESC, vendor_extracted
""")

payment_transactions = cur.fetchall()

print(f"\nFound {len(payment_transactions)} CARD PAYMENT transactions\n")
print("-" * 80)

nsf_indicators = ['NSF', 'NON-SUFFICIENT', 'INSUFFICIENT', 'RETURNED', 'DISHONORED']
chargeback_indicators = ['CHARGEBACK', 'REVERSAL', 'REFUND', 'GBL', 'GLOBAL']

nsf_count = 0
chargeback_count = 0
unclear_count = 0

for date, desc, vendor, debit, credit, category in payment_transactions:
    desc_upper = desc.upper() if desc else ''
    
    is_nsf = any(indicator in desc_upper for indicator in nsf_indicators)
    is_chargeback = any(indicator in desc_upper for indicator in chargeback_indicators)
    
    # Display all to review
    amount = f"${debit:,.2f}" if debit else f"(${credit:,.2f})"
    
    if is_nsf:
        print(f"⚠️  NSF: {date} | {vendor} | {amount}")
        print(f"    {desc}")
        nsf_count += 1
    elif is_chargeback:
        print(f"✅ Chargeback: {date} | {vendor} | {amount}")
        print(f"    {desc}")
        chargeback_count += 1
    else:
        print(f"❓ UNCLEAR: {date} | {vendor} | {amount}")
        print(f"    {desc}")
        unclear_count += 1
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total CARD PAYMENT transactions: {len(payment_transactions)}")
print(f"  ✅ Chargebacks/Reversals: {chargeback_count}")
print(f"  ⚠️  NSF charges: {nsf_count}")
print(f"  ❓ Unclear: {unclear_count}")

if nsf_count > 0:
    print("\n⚠️  WARNING: Found NSF charges incorrectly categorized as CARD PAYMENT")
    print("   These should be renamed to reflect NSF fees, not Global Payments")
else:
    print("\n✅ All CARD PAYMENT transactions appear legitimate")

# Also check for any NSF in card deposits
print("\n" + "=" * 80)
print("CHECKING CARD DEPOSITS FOR NSF")
print("=" * 80)

cur.execute("""
    SELECT 
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE vendor_extracted IN ('VCARD DEPOSIT', 'MCARD DEPOSIT', 'ACARD DEPOSIT', 'DCARD DEPOSIT')
    AND (
        UPPER(description) LIKE '%NSF%'
        OR UPPER(description) LIKE '%NON-SUFFICIENT%'
        OR UPPER(description) LIKE '%INSUFFICIENT%'
        OR UPPER(description) LIKE '%RETURNED%'
    )
    ORDER BY transaction_date DESC
""")

nsf_deposits = cur.fetchall()

if nsf_deposits:
    print(f"\n⚠️  Found {len(nsf_deposits)} CARD DEPOSIT transactions with NSF indicators:\n")
    for date, desc, vendor, debit, credit in nsf_deposits:
        amount = f"${debit:,.2f}" if debit else f"(${credit:,.2f})"
        print(f"{date} | {vendor} | {amount}")
        print(f"  {desc}\n")
else:
    print("\n✅ No NSF indicators found in CARD DEPOSIT transactions")

cur.close()
conn.close()

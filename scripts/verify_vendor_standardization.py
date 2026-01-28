#!/usr/bin/env python3
"""
Verify all vendor standardization changes are committed in database.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("VENDOR STANDARDIZATION VERIFICATION")
print("=" * 80)

# 1. Check VCARD/MCARD/ACARD naming
print("\n1. GLOBAL PAYMENTS SHORT FORM (VCARD/MCARD/ACARD)")
print("-" * 80)

cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name LIKE '%CARD DEPOSIT'
       OR vendor_name LIKE '%CARD PAYMENT'
    GROUP BY vendor_name
    ORDER BY count DESC
""")
card_receipts = cur.fetchall()

cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count, SUM(debit_amount + credit_amount) as total
    FROM banking_transactions
    WHERE vendor_extracted LIKE '%CARD DEPOSIT'
       OR vendor_extracted LIKE '%CARD PAYMENT'
    GROUP BY vendor_extracted
    ORDER BY count DESC
""")
card_banking = cur.fetchall()

print("Receipts:")
for vendor, count, total in card_receipts:
    print(f"  {vendor:30} {count:5} records  ${total:,.2f}")

print("\nBanking:")
for vendor, count, total in card_banking:
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"  {vendor:30} {count:5} records  {total_str}")

# 2. Check CASH WITHDRAWAL standardization
print("\n\n2. CASH WITHDRAWAL STANDARDIZATION")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'CASH WITHDRAWAL'
""")
cash_count, cash_total = cur.fetchone()
print(f"CASH WITHDRAWAL: {cash_count} receipts, ${cash_total:,.2f}")

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name LIKE '%ATM%'
       OR vendor_name LIKE '%ABM%'
""")
remaining_atm = cur.fetchone()[0]
print(f"Remaining ATM/ABM: {remaining_atm} (should be 0)")

# 3. Check gas station standardization
print("\n\n3. GAS STATION STANDARDIZATION")
print("-" * 80)

gas_stations = [
    'ESSO', 'MOHAWK', 'CIRCLE K', 'SHELL', 'PETRO CANADA',
    'HUSKY', 'CO-OP', 'FAS GAS', "RUN'N ON EMPTY"
]

for station in gas_stations:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name = %s
    """, (station,))
    count, total = cur.fetchone()
    if count and count > 0:
        print(f"  {station:20} {count:4} receipts  ${total:,.2f}")

# 4. Check EMAIL TRANSFER standardization
print("\n\n4. EMAIL TRANSFER STANDARDIZATION")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'EMAIL TRANSFER'
""")
email_count, email_total = cur.fetchone()
print(f"EMAIL TRANSFER: {email_count} receipts, ${email_total:,.2f}")

# 5. Check UNKNOWN elimination
print("\n\n5. UNKNOWN VENDOR ELIMINATION")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
""")
unknown_count = cur.fetchone()[0]
print(f"UNKNOWN vendors: {unknown_count} (should be 0)")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'HISTORICAL - UNVERIFIED'
""")
historical_count, historical_total = cur.fetchone()
print(f"HISTORICAL - UNVERIFIED: {historical_count} receipts, ${historical_total:,.2f}")

# 6. Check NSF standardization
print("\n\n6. NSF CHARGE STANDARDIZATION")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*), SUM(debit_amount)
    FROM banking_transactions
    WHERE vendor_extracted = 'NSF CHARGE'
""")
nsf_count, nsf_total = cur.fetchone()
nsf_total_str = f"${nsf_total:,.2f}" if nsf_total else "$0.00"
print(f"NSF CHARGE: {nsf_count} banking records, {nsf_total_str}")

# 7. Check bank fee standardization
print("\n\n7. BANK FEE STANDARDIZATION")
print("-" * 80)

fee_vendors = ['BANK SERVICE FEE', 'OVERDRAFT FEE', 'CHECK PAYMENT']
for fee in fee_vendors:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name = %s
    """, (fee,))
    count, total = cur.fetchone()
    if count and count > 0:
        total_str = f"${total:,.2f}" if total else "$0.00"
        print(f"  {fee:20} {count:4} receipts  {total_str}")

# Summary
print("\n\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

cur.execute("SELECT COUNT(*) FROM receipts")
total_receipts = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM banking_transactions")
total_banking = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT vendor_name)
    FROM receipts
    WHERE vendor_name IS NOT NULL
""")
unique_vendors = cur.fetchone()[0]

print(f"\nTotal receipts: {total_receipts:,}")
print(f"Total banking transactions: {total_banking:,}")
print(f"Unique vendors: {unique_vendors:,}")
print(f"UNKNOWN vendors: {unknown_count} ✅" if unknown_count == 0 else f"UNKNOWN vendors: {unknown_count} ⚠️")
print(f"Historical (pre-2012): {historical_count}")

# Check for any suspicious patterns
print("\n\n8. POTENTIAL ISSUES CHECK")
print("-" * 80)

cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name LIKE '%GLOBAL%'
       OR vendor_name LIKE '%GBL%'
    GROUP BY vendor_name
""")
global_remaining = cur.fetchall()
if global_remaining:
    print("⚠️  Found long-form Global Payments names:")
    for vendor, count in global_remaining:
        print(f"  {vendor}: {count} records")
else:
    print("✅ No long-form Global Payments names found")

cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name LIKE 'Point of Sale%'
       OR vendor_name LIKE '%#%#%'
    GROUP BY vendor_name
    LIMIT 10
""")
pos_remaining = cur.fetchall()
if pos_remaining:
    print("\n⚠️  Found Point of Sale patterns:")
    for vendor, count in pos_remaining:
        print(f"  {vendor}: {count} records")
else:
    print("✅ No Point of Sale patterns found")

cur.close()
conn.close()

print("\n✅ VERIFICATION COMPLETE")

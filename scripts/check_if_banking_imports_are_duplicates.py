"""
Check if banking import vendor payments are duplicates or unique (NSF, reversals, etc.)
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Get the vendor payments from receipts (banking imports)
known_vendors = [
    'WCB', 'WORKERS COMPENSATION', 'FAS GAS', 'SHELL', 'PETRO', 'ESSO',
    'TELUS', 'SHAW', 'ENMAX', 'LEASE', 'INSURANCE', 'CRA', 'REVENUE',
    'ATB', 'CIBC', 'SCOTIA', 'MASTERCARD', 'VISA', 'AMEX',
    '106.7', 'KOOL', 'RADIO', 'ADVERTISING', 'CO-OP', 'DAIRY QUEEN',
    'TIM HORTONS', 'NOFRILLS', 'ROGERS', 'SERVICE CHARGE', 'CASH WITHDRAWAL'
]

print("=== Checking if Banking Import Vendor Payments are Duplicates ===\n")

# Find all vendor payment receipts
vendor_pattern = ' OR '.join([f"vendor_name ILIKE '%{v}%'" for v in known_vendors])
cur.execute(f"""
    SELECT receipt_id, vendor_name, source_reference, receipt_date, 
           gross_amount, description, banking_transaction_id,
           created_from_banking
    FROM receipts
    WHERE (created_from_banking = true OR source_reference = 'BANKING_IMPORT')
      AND ({vendor_pattern} OR gross_amount < 0)
    ORDER BY receipt_date
""")

vendor_receipts = cur.fetchall()
print(f"Total vendor payment receipts from banking: {len(vendor_receipts)}\n")

# Categorize them
duplicates = []  # Also exists as actual vendor receipt (different receipt_id)
nsf_reversals = []  # NSF or reversal (negative amount, description indicates reversal)
unique_banking_only = []  # Only in banking, not recorded elsewhere

for row in vendor_receipts:
    receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id, created_banking = row
    
    # Check if it's negative (likely NSF, reversal, or withdrawal)
    if amount and amount < 0:
        # Check description for NSF indicators
        desc_lower = (desc or '').lower()
        if any(x in desc_lower for x in ['nsf', 'reversal', 'withdrawal', 'atm', 'cash', 'service charge']):
            nsf_reversals.append(row)
        else:
            nsf_reversals.append(row)  # All negatives treated as NSF/reversals
        continue
    
    # For positive amounts, check if there's a matching vendor receipt
    if vendor_name and amount:
        # Look for matching vendor receipt (same vendor, similar date, similar amount)
        cur.execute("""
            SELECT receipt_id, source_reference, receipt_date, gross_amount
            FROM receipts
            WHERE receipt_id != %s
              AND vendor_name = %s
              AND ABS(gross_amount - %s) < 0.01
              AND receipt_date BETWEEN (%s::date - INTERVAL '7 days') AND (%s::date + INTERVAL '7 days')
              AND created_from_banking = false
        """, (receipt_id, vendor_name, amount, date, date))
        
        matches = cur.fetchall()
        if matches:
            duplicates.append((row, matches))
        else:
            unique_banking_only.append(row)
    else:
        unique_banking_only.append(row)

print("=" * 80)
print("🔁 DUPLICATES - Also recorded as vendor receipts elsewhere")
print("=" * 80)
if duplicates:
    print(f"\nFound {len(duplicates)} duplicates:\n")
    total_dup = 0
    for orig, matches in duplicates[:20]:  # Show first 20
        receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id, created_banking = orig
        print(f"Receipt {receipt_id}: {vendor_name}, ${amount:,.2f} on {date}")
        print(f"  Matches found:")
        for m in matches:
            print(f"    - Receipt {m[0]}: {m[1]}, ${m[3]:,.2f} on {m[2]}")
        print()
        total_dup += (amount or 0)
    
    if len(duplicates) > 20:
        print(f"... and {len(duplicates) - 20} more duplicates")
    print(f"\nTotal duplicate amount: ${total_dup:,.2f}")
else:
    print("✅ No duplicates found")

print("\n" + "=" * 80)
print("↩️ NSF / REVERSALS / WITHDRAWALS (negative amounts or special transactions)")
print("=" * 80)
if nsf_reversals:
    print(f"\nFound {len(nsf_reversals)} NSF/reversal transactions:\n")
    total_nsf = 0
    
    # Group by type
    withdrawals = [r for r in nsf_reversals if 'WITHDRAWAL' in (r[5] or '').upper() or 'ATM' in (r[5] or '').upper()]
    service_charges = [r for r in nsf_reversals if 'SERVICE CHARGE' in (r[5] or '').upper() or 'FEE' in (r[5] or '').upper()]
    actual_nsf = [r for r in nsf_reversals if 'NSF' in (r[5] or '').upper() or 'REVERSAL' in (r[5] or '').upper()]
    other_negative = [r for r in nsf_reversals if r not in withdrawals and r not in service_charges and r not in actual_nsf]
    
    print(f"  Cash Withdrawals/ATM: {len(withdrawals)}")
    print(f"  Service Charges/Fees: {len(service_charges)}")
    print(f"  NSF/Reversals: {len(actual_nsf)}")
    print(f"  Other negative: {len(other_negative)}\n")
    
    print("Sample (first 10):")
    for row in nsf_reversals[:10]:
        receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id, created_banking = row
        amt_str = f"${amount:,.2f}" if amount is not None else "$0.00"
        print(f"  Receipt {receipt_id}: {vendor_name or '(no vendor)'}, {amt_str} on {date}")
        if desc:
            print(f"    {desc[:100]}")
        total_nsf += (amount or 0)
    
    print(f"\nTotal NSF/reversal amount: ${total_nsf:,.2f}")
else:
    print("None")

print("\n" + "=" * 80)
print("📌 UNIQUE - Only in banking, not recorded as vendor receipts elsewhere")
print("=" * 80)
if unique_banking_only:
    print(f"\nFound {len(unique_banking_only)} unique banking-only vendor transactions:\n")
    total_unique = 0
    
    # Sample by vendor type
    gas_stations = [r for r in unique_banking_only if any(g in (r[1] or '').upper() for g in ['SHELL', 'ESSO', 'PETRO', 'CO-OP', 'FAS GAS'])]
    utilities = [r for r in unique_banking_only if any(u in (r[1] or '').upper() for u in ['TELUS', 'SHAW', 'ENMAX', 'ROGERS'])]
    wcb = [r for r in unique_banking_only if 'WCB' in (r[1] or '').upper()]
    other_vendors = [r for r in unique_banking_only if r not in gas_stations and r not in utilities and r not in wcb]
    
    print(f"  Gas stations: {len(gas_stations)}")
    print(f"  Utilities: {len(utilities)}")
    print(f"  WCB: {len(wcb)}")
    print(f"  Other vendors: {len(other_vendors)}\n")
    
    print("Sample (first 15):")
    for row in unique_banking_only[:15]:
        receipt_id, vendor_name, source_ref, date, amount, desc, bank_tx_id, created_banking = row
        amt_str = f"${amount:,.2f}" if amount is not None else "$0.00"
        print(f"  Receipt {receipt_id}: {vendor_name}, {amt_str} on {date}")
        total_unique += (amount or 0)
    
    if len(unique_banking_only) > 15:
        print(f"\n... and {len(unique_banking_only) - 15} more unique transactions")
    print(f"\nTotal unique amount: ${total_unique:,.2f}")
else:
    print("None")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total vendor payments in receipts (from banking): {len(vendor_receipts)}")
print(f"  🔁 Duplicates (can be deleted): {len(duplicates)}")
print(f"  ↩️  NSF/Reversals/Withdrawals (negative, keep): {len(nsf_reversals)}")
print(f"  📌 Unique banking-only (investigate): {len(unique_banking_only)}")

cur.close()
conn.close()

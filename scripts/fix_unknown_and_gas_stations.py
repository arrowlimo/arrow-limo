#!/usr/bin/env python3
"""
Fix remaining vendor issues:
1. Extract vendors from UNKNOWN 
2. Standardize gas stations (ESSO, MOHAWK, DOMO, CIRCLE K, etc.)
3. Clean RUN'N ON EMPTY to remove addresses
"""

import psycopg2
import re

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

print("=" * 80)
print("FIXING UNKNOWN VENDORS AND GAS STATION VARIATIONS")
print("=" * 80)

cur = conn.cursor()

# 1. Check UNKNOWN vendors
print("\n1. ANALYZING UNKNOWN VENDORS")
print("-" * 80)

cur.execute("""
    SELECT description, COUNT(*) as count
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
    GROUP BY description
    ORDER BY COUNT(*) DESC
    LIMIT 50
""")

unknown_vendors = cur.fetchall()
print(f"\nFound {len(unknown_vendors)} UNKNOWN vendor patterns\n")
for desc, count in unknown_vendors[:20]:
    print(f"{count:4} | {desc[:70]}")

# 2. Check gas station variations
print("\n\n2. GAS STATION VARIATIONS")
print("-" * 80)

gas_patterns = [
    'ESSO',
    'MOHAWK',
    'DOMO',
    'CIRCLE K',
    "SCOTTY'S",
    'SHELL',
    'PETRO CANADA',
    'HUSKY',
    'CO-OP',
    'FAS GAS',
    "RUN'N ON EMPTY"
]

for pattern in gas_patterns:
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        WHERE vendor_name LIKE %s
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
    """, (f'%{pattern}%',))
    
    variations = cur.fetchall()
    if variations:
        total = sum(count for _, count in variations)
        print(f"\n{pattern}: {total} receipts, {len(variations)} variations")
        for vendor, count in variations[:5]:
            print(f"  {count:4} | {vendor}")
        if len(variations) > 5:
            print(f"  ... and {len(variations) - 5} more")

# 3. Show preview of fixes
print("\n\n" + "=" * 80)
print("PREVIEW OF FIXES")
print("=" * 80)

def extract_vendor_from_unknown(description):
    """Try to extract vendor from UNKNOWN descriptions."""
    if not description:
        return 'UNKNOWN'
    
    desc = description.upper()
    
    # Card deposits
    if 'VCARD DEPOSIT' in desc or 'VISA DEPOSIT' in desc:
        return 'VCARD DEPOSIT'
    if 'MCARD DEPOSIT' in desc or 'MASTERCARD DEPOSIT' in desc:
        return 'MCARD DEPOSIT'
    if 'ACARD DEPOSIT' in desc or 'AMEX DEPOSIT' in desc:
        return 'ACARD DEPOSIT'
    if 'DCARD DEPOSIT' in desc or 'DEBIT DEPOSIT' in desc:
        return 'DCARD DEPOSIT'
    
    # Cash withdrawals
    if 'CASH WITHDRAWAL' in desc or 'ATM WITHDRAWAL' in desc or 'ABM WITHDRAWAL' in desc:
        return 'CASH WITHDRAWAL'
    
    # Fees
    if 'OD FEE' in desc or 'OVERDRAFT FEE' in desc:
        return 'OVERDRAFT FEE'
    if 'BANK FEE' in desc or 'BANK SERVICE' in desc:
        return 'BANK SERVICE FEE'
    if 'GBL MERCH FEE' in desc or 'MERCHANT FEE' in desc:
        return 'MERCHANT FEE'
    
    # Common vendors
    if 'HEFFNER' in desc:
        return 'HEFFNER AUTO FINANCE'
    if 'SQUARE' in desc and 'INC' in desc:
        return 'SQUARE'
    if 'E-TRANSFER' in desc or 'ETRANSFER' in desc or 'EMAIL TRANSFER' in desc:
        return 'EMAIL TRANSFER'
    if 'NSF' in desc:
        return 'NSF CHARGE'
    if 'TELUS' in desc:
        return 'TELUS'
    if 'SHAW' in desc:
        return 'SHAW CABLE'
    if 'ROGERS' in desc:
        return 'ROGERS'
    if 'CENTEX' in desc:
        return 'CENTEX'
    if 'LIQUOR BARN' in desc:
        return 'LIQUOR BARN'
    if 'LEASE FINANCE' in desc or 'LFG BUSINESS' in desc:
        return 'LEASE FINANCE GROUP'
    if "RUN'N ON EMPTY" in desc or "RUN N ON EMPTY" in desc:
        return "RUN'N ON EMPTY"
    if 'ERLES AUTO' in desc:
        return 'ERLES AUTO REPAIR'
    if 'JACK CARTER' in desc:
        return 'JACK CARTER'
    if 'AMERICAN EXPRESS PAYMENT' in desc or 'AMEX PAYMENT' in desc:
        return 'AMERICAN EXPRESS PAYMENT'
    if 'COOP INSURANCE' in desc or 'CSI' in desc:
        return 'CO-OP INSURANCE'
    if 'ACE TRUCK' in desc:
        return 'ACE TRUCK RENTALS'
    if 'STAPLES' in desc:
        return 'STAPLES'
    if 'FAS GAS' in desc:
        return 'FAS GAS'
    if 'ESSO' in desc:
        return 'ESSO'
    if 'REAL CANADIAN' in desc or 'SUPERSTORE' in desc:
        return 'SUPERSTORE'
    if 'DEPOSIT' in desc and 'DEBIT' in desc:
        return 'DEPOSIT'
    
    return 'UNKNOWN'

def standardize_gas_station(vendor):
    """Standardize gas station names."""
    if not vendor:
        return vendor
    
    # ESSO variations
    if 'ESSO' in vendor:
        if 'SCOTTY' in vendor or "SCOTTY'S" in vendor:
            return "SCOTTY'S ESSO"
        return 'ESSO'
    
    # MOHAWK
    if 'MOHAWK' in vendor:
        return 'MOHAWK'
    
    # DOMO
    if 'DOMO' in vendor:
        return 'DOMO'
    
    # CIRCLE K
    if 'CIRCLE K' in vendor:
        return 'CIRCLE K'
    
    # RUN'N ON EMPTY (remove addresses)
    if "RUN'N ON EMPTY" in vendor or "RUN N ON EMPTY" in vendor:
        return "RUN'N ON EMPTY"
    
    # SHELL (remove addresses/numbers)
    if 'SHELL' in vendor:
        return 'SHELL'
    
    # PETRO CANADA
    if 'PETRO CANADA' in vendor or 'PETRO-CANADA' in vendor:
        return 'PETRO CANADA'
    
    # HUSKY
    if 'HUSKY' in vendor:
        return 'HUSKY'
    
    # CO-OP
    if 'CO-OP' in vendor or 'COOP' in vendor:
        return 'CO-OP'
    
    # FAS GAS
    if 'FAS GAS' in vendor:
        return 'FAS GAS'
    
    return vendor

# Preview UNKNOWN fixes
cur.execute("""
    SELECT vendor_name, description, COUNT(*) as count
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
    GROUP BY vendor_name, description
    ORDER BY COUNT(*) DESC
    LIMIT 100
""")

unknown_fixes = {}
for vendor, desc, count in cur.fetchall():
    new_vendor = extract_vendor_from_unknown(desc)
    if new_vendor != 'UNKNOWN':
        if new_vendor not in unknown_fixes:
            unknown_fixes[new_vendor] = 0
        unknown_fixes[new_vendor] += count

print("\nUNKNOWN vendors that can be fixed:")
for vendor, count in sorted(unknown_fixes.items(), key=lambda x: x[1], reverse=True):
    print(f"  → {vendor}: {count} receipts")

# Preview gas station fixes
cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
""")

gas_fixes = {}
for vendor, count in cur.fetchall():
    standardized = standardize_gas_station(vendor)
    if standardized != vendor:
        if standardized not in gas_fixes:
            gas_fixes[standardized] = []
        gas_fixes[standardized].append((vendor, count))

print("\nGas station standardizations:")
for new_name, variations in sorted(gas_fixes.items(), key=lambda x: sum(c for _, c in x[1]), reverse=True):
    total = sum(count for _, count in variations)
    print(f"\n→ {new_name}: {total} receipts from {len(variations)} variations")
    for old_name, count in sorted(variations, key=lambda x: x[1], reverse=True)[:3]:
        print(f"    {old_name}: {count}")
    if len(variations) > 3:
        print(f"    ... and {len(variations) - 3} more")

total_unknown_fixed = sum(unknown_fixes.values())
total_gas_fixed = sum(sum(c for _, c in v) for v in gas_fixes.values())

print("\n" + "=" * 80)
print(f"Total receipts to update:")
print(f"  UNKNOWN fixes: {total_unknown_fixed}")
print(f"  Gas station fixes: {total_gas_fixed}")
print(f"  TOTAL: {total_unknown_fixed + total_gas_fixed}")
print("=" * 80)

confirm = input("\nProceed with fixes? (yes/no): ").strip().lower()

if confirm == 'yes':
    print("\n📝 Fixing UNKNOWN vendors...")
    
    cur.execute("""
        SELECT receipt_id, vendor_name, description
        FROM receipts
        WHERE vendor_name = 'UNKNOWN'
    """)
    
    unknown_count = 0
    for receipt_id, vendor, desc in cur.fetchall():
        new_vendor = extract_vendor_from_unknown(desc)
        if new_vendor != 'UNKNOWN':
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s
                WHERE receipt_id = %s
            """, (new_vendor, receipt_id))
            unknown_count += cur.rowcount
    
    print(f"   Fixed {unknown_count} UNKNOWN vendors")
    
    print("\n📝 Standardizing gas stations...")
    
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE vendor_name IS NOT NULL
    """)
    
    gas_count = 0
    for receipt_id, vendor in cur.fetchall():
        standardized = standardize_gas_station(vendor)
        if standardized != vendor:
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s
                WHERE receipt_id = %s
            """, (standardized, receipt_id))
            gas_count += cur.rowcount
    
    print(f"   Standardized {gas_count} gas station names")
    
    print("\n💾 Committing changes...")
    conn.commit()
    
    print("\n✅ FIXES COMPLETE")
    print(f"   UNKNOWN fixed: {unknown_count}")
    print(f"   Gas stations: {gas_count}")
    
    # Show top vendors
    print("\n\nTop vendors after fixes:")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    for vendor, count in cur.fetchall():
        print(f"  {vendor}: {count:,}")

else:
    print("\n❌ Fixes cancelled")

cur.close()
conn.close()

#!/usr/bin/env python3
"""
Check for remaining vague/generic vendor names.

Looking for:
- POINT OF
- ABM / ATM
- CUSTOMER
- BANK / BANKING TRANSACTION
- BRANCH TRANSACTION
- Any other vague generic names
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 80)
print("CHECKING FOR VAGUE/GENERIC VENDOR NAMES")
print("=" * 80)

# Check for each vague vendor type
vague_vendors = [
    ("POINT OF", "Generic point of sale"),
    ("CUSTOMER", "Generic customer"),
    ("BANK", "Generic bank (not specific bank name)"),
    ("BANKING TRANSACTION", "Generic banking transaction"),
    ("BRANCH TRANSACTION", "Generic branch transaction"),
    ("ATM", "Generic ATM (not specific location)"),
    ("ABM", "Generic ABM"),
    ("AUTOMATED BANKING MACHINE", "Generic ABM"),
    ("CASH WITHDRAWAL", "Generic cash withdrawal (should be specific location)"),
    ("BRANCH WITHDRAWAL", "Generic branch withdrawal"),
]

print("\nSearching for vague vendor names:\n")

total_vague = 0
all_vague_receipts = []

for pattern, description in vague_vendors:
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE vendor_name LIKE %s
        GROUP BY vendor_name
        ORDER BY count DESC
    """, (f'%{pattern}%',))
    
    results = cur.fetchall()
    
    if results:
        print(f"⚠️  {description.upper()}:")
        for vendor, count, amount in results:
            print(f"  {vendor[:60]:60} {count:>6,} receipts  ${amount:>12,.2f}")
            total_vague += count
            all_vague_receipts.append((vendor, count, amount))
        print()

# Check for single-word generic vendors
print("\nChecking for other single-word generic vendors:")
cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE vendor_name NOT LIKE '%-%'
      AND vendor_name NOT LIKE '% %'
      AND LENGTH(vendor_name) < 10
      AND vendor_name NOT IN (
          'SOBEYS', 'SAFEWAY', 'WALMART', 'COSTCO', 'SHELL', 'ESSO',
          'PETRO', 'HUSKY', 'COOP', 'CO-OP', 'LIQUOR', 'BEER'
      )
    GROUP BY vendor_name
    ORDER BY count DESC
    LIMIT 20
""")

short_vendors = cur.fetchall()
if short_vendors:
    print("\nShort/generic vendor names (may need review):")
    for vendor, count, amount in short_vendors:
        print(f"  {vendor[:60]:60} {count:>6,} receipts  ${amount:>12,.2f}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if total_vague > 0:
    print(f"\n❌ FOUND {total_vague:,} receipts with vague/generic vendor names")
    print("\nTop 10 vague vendors:")
    all_vague_receipts.sort(key=lambda x: x[1], reverse=True)
    for vendor, count, amount in all_vague_receipts[:10]:
        print(f"  {vendor[:60]:60} {count:>6,} receipts  ${amount:>12,.2f}")
else:
    print("\n✅ NO VAGUE/GENERIC VENDOR NAMES FOUND!")
    print("All vendors are specific and matchable")

# Check specific examples user mentioned
print("\n" + "=" * 80)
print("USER-SPECIFIED CHECKS")
print("=" * 80)

checks = [
    ("POINT OF", "Point of sale transactions"),
    ("ABM", "Automated banking machines"),
    ("CUSTOMER", "Generic customer"),
    ("BANK", "Generic bank references"),
]

all_clean = True
for pattern, desc in checks:
    cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = %s", (pattern,))
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"❌ {desc:40} {count:>6,} receipts with exact match '{pattern}'")
        all_clean = False
    else:
        print(f"✅ {desc:40} 0 receipts (clean!)")

if all_clean:
    print("\n🎉 ALL USER-SPECIFIED VAGUE VENDORS ARE CLEANED UP!")

cur.close()
conn.close()

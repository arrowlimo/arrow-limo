#!/usr/bin/env python3
"""Fix missing GL account names in chart_of_accounts."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("FIX MISSING GL ACCOUNT NAMES")
print("="*100)

# 1. Identify GL codes with missing names
print("\n1. GL codes with missing or blank names:")
print("-"*100)

cur.execute("""
    SELECT 
        account_code,
        account_name,
        account_type,
        COUNT(r.receipt_id) as receipt_count,
        SUM(r.gross_amount) as total_amount
    FROM chart_of_accounts c
    LEFT JOIN receipts r ON r.gl_account_code = c.account_code
    WHERE c.account_name IS NULL OR c.account_name = '' OR TRIM(c.account_name) = ''
    GROUP BY c.account_code, c.account_name, c.account_type
    ORDER BY COUNT(r.receipt_id) DESC
""")

missing_names = cur.fetchall()
print(f"{'GL Code':<10} {'Current Name':<30} {'Type':<15} {'Receipts':<10} {'Amount'}")
print("-"*100)

for code, name, acct_type, count, amount in missing_names:
    name_display = (name or "BLANK")[:30]
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{code:<10} {name_display:<30} {acct_type or 'N/A':<15} {count:<10} {amount_str}")

# 2. Define names for common GL codes based on usage
print("\n2. Proposed GL Account Names:")
print("-"*100)

gl_name_mappings = {
    '5900': 'Other Operating Expenses',
    '6900': 'Miscellaneous Expenses',
    '5310': 'Beverages - Customer Service',
    '5315': 'Beverages - Business Entertainment',
    '5355': 'Vehicle Supplies & Maintenance',
    '5470': 'Food & Snacks',
    '5116': 'Client Amenities - Food, Coffee, Supplies',
    '5850': 'Mixed-Use Expenses',
    '6500': 'Professional Development',
    '6300': 'Office Equipment & Supplies',
    '6100': 'Printing & Copying',
    '5330': 'Property Insurance',
    '5400': 'Office & Administrative',
    '5120': 'Vehicle Maintenance & Repairs',
    '6950': 'Loss on Asset Disposal',
    '6400': 'Insurance',
    '2200': 'Accrued Expenses',
    '6700': 'Other Expenses',
}

for code, proposed_name in gl_name_mappings.items():
    # Check if this code exists and is missing a name
    cur.execute("""
        SELECT account_code, account_name 
        FROM chart_of_accounts 
        WHERE account_code = %s
        AND (account_name IS NULL OR account_name = '' OR TRIM(account_name) = '')
    """, (code,))
    
    result = cur.fetchone()
    if result:
        print(f"  {code} → {proposed_name}")

# 3. Update GL account names
print("\n3. Updating GL account names...")
print("-"*100)

updates_made = 0
for code, name in gl_name_mappings.items():
    cur.execute("""
        UPDATE chart_of_accounts
        SET account_name = %s
        WHERE account_code = %s
        AND (account_name IS NULL OR account_name = '' OR TRIM(account_name) = '')
    """, (name, code))
    
    if cur.rowcount > 0:
        print(f"  ✓ Updated {code} → {name}")
        updates_made += cur.rowcount

conn.commit()

print(f"\n✓ Updated {updates_made} GL account names")

# 4. Update receipts to use the new names
print("\n4. Updating receipt GL account names...")
print("-"*100)

cur.execute("""
    UPDATE receipts r
    SET gl_account_name = c.account_name
    FROM chart_of_accounts c
    WHERE r.gl_account_code = c.account_code
    AND (r.gl_account_name IS NULL OR r.gl_account_name = '' OR r.gl_account_name != c.account_name)
    AND c.account_name IS NOT NULL
    AND c.account_name != ''
""")

receipts_updated = cur.rowcount
conn.commit()

print(f"✓ Updated {receipts_updated:,} receipts with proper GL account names")

# 5. Verify
print("\n5. Verification - Receipts with missing GL names:")
print("-"*100)

cur.execute("""
    SELECT 
        gl_account_code,
        gl_account_name,
        COUNT(*) as count
    FROM receipts
    WHERE gl_account_code IS NOT NULL
    AND (gl_account_name IS NULL OR gl_account_name = '')
    GROUP BY gl_account_code, gl_account_name
    ORDER BY count DESC
    LIMIT 10
""")

still_missing = cur.fetchall()
if still_missing:
    print(f"{'GL Code':<10} {'GL Name':<30} {'Count'}")
    print("-"*100)
    for code, name, count in still_missing:
        print(f"{code:<10} {name or 'BLANK':<30} {count}")
else:
    print("✓ All receipts with GL codes now have GL account names!")

print("\n" + "="*100)
print("COMPLETE")
print("="*100)
print(f"""
✓ Updated {updates_made} GL account definitions
✓ Updated {receipts_updated:,} receipt GL account names
✓ GL codes now have proper descriptive names for accounting
""")

conn.close()

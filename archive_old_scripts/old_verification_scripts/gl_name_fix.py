import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', password='ArrowLimousine', dbname='almsdata')
cur = conn.cursor()

results = []

# Fix GL names
gl_names = {
    '5900': 'Other Operating Expenses',
    '6900': 'Miscellaneous Expenses',
    '5310': 'Beverages - Customer Service',
    '5315': 'Beverages - Business Entertainment',
    '5355': 'Vehicle Supplies & Maintenance',
    '5470': 'Food & Snacks',
    '5850': 'Mixed-Use Expenses',
    '6500': 'Professional Development',
    '6300': 'Office Equipment & Supplies',
    '6100': 'Printing & Copying',
    '5330': 'Property Insurance',
    '5120': 'Vehicle Maintenance & Repairs',
    '6950': 'Loss on Asset Disposal',
    '2200': 'Accrued Expenses',
    '6700': 'Other Expenses',
}

updated = 0
for code, name in gl_names.items():
    cur.execute("""
        UPDATE chart_of_accounts
        SET account_name = %s
        WHERE account_code = %s
        AND (account_name IS NULL OR account_name = '' OR TRIM(account_name) = '')
    """, (name, code))
    if cur.rowcount > 0:
        updated += cur.rowcount
        results.append(f"{code} → {name}")

conn.commit()

# Update receipts
cur.execute("""
    UPDATE receipts r
    SET gl_account_name = c.account_name
    FROM chart_of_accounts c
    WHERE r.gl_account_code = c.account_code
    AND c.account_name IS NOT NULL
    AND c.account_name != ''
    AND (r.gl_account_name IS NULL OR r.gl_account_name = '' OR r.gl_account_name != c.account_name)
""")

receipts_updated = cur.rowcount
conn.commit()
conn.close()

# Write to file
with open('l:\\limo\\gl_name_fix_results.txt', 'w') as f:
    f.write("GL ACCOUNT NAME FIXES\n")
    f.write("="*50 + "\n\n")
    for r in results:
        f.write(f"  ✓ {r}\n")
    f.write(f"\nUpdated {updated} GL account names\n")
    f.write(f"Updated {receipts_updated:,} receipts\n")

print(f"Results in l:\\limo\\gl_name_fix_results.txt")

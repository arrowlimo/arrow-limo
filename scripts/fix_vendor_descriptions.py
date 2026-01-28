#!/usr/bin/env python3
"""
Fix vendor name and description issues:
1. "604 - LB 67TH ST.        RED D" → "LIQUOR BARN"
2. Remove trailing "D" and "DRYDE" from descriptions
3. Fix 2012-05-15 "« EMT Dave Richard X" and similar garbled entries
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('FIXING VENDOR NAMES AND DESCRIPTIONS')
print('='*80)
print()

# Fix 1: "604 - LB 67TH ST.        RED D" → "LIQUOR BARN"
print('STEP 1: Fix Liquor Barn vendor names')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) FROM receipts 
    WHERE vendor_name LIKE '604 - LB 67TH ST%'
""")
count = cur.fetchone()[0]
print(f'Found {count} "604 - LB 67TH ST" entries')

cur.execute("""
    UPDATE receipts 
    SET vendor_name = 'LIQUOR BARN'
    WHERE vendor_name LIKE '604 - LB 67TH ST%'
""")
updated1 = cur.rowcount
print(f'✅ Updated {updated1} vendor names to "LIQUOR BARN"')
print()

# Fix 2: Remove trailing "D" and "DRYDE" from vendor names
print('STEP 2: Fix vendor names with trailing "D" or "DRYDE"')
print('-'*80)

cur.execute("""
    SELECT COUNT(*) FROM receipts 
    WHERE vendor_name LIKE '%RED D' OR vendor_name LIKE '%DRYDE'
""")
count = cur.fetchone()[0]
print(f'Found {count} entries with trailing "D" or "DRYDE"')

# Fix "RED D" endings
cur.execute("""
    UPDATE receipts 
    SET vendor_name = TRIM(REGEXP_REPLACE(vendor_name, '\\s+RED D$', '', 'g'))
    WHERE vendor_name LIKE '%RED D'
""")
updated2a = cur.rowcount
print(f'✅ Fixed {updated2a} vendor names with "RED D" suffix')

# Fix "DRYDE" endings
cur.execute("""
    UPDATE receipts 
    SET vendor_name = TRIM(REGEXP_REPLACE(vendor_name, '\\s+DRYDE$', '', 'g'))
    WHERE vendor_name LIKE '%DRYDE'
""")
updated2b = cur.rowcount
print(f'✅ Fixed {updated2b} vendor names with "DRYDE" suffix')
print()

# Fix 3: Clean up 2012-05-15 garbled entries
print('STEP 3: Fix 2012-05-15 garbled vendor names')
print('-'*80)

garbled_fixes = [
    ('« EMT Dave Richard X', 'David Richard'),
    ('w/d Paul Richard (v) X', 'Paul Richard'),
    ('dd Centex X', 'Centex'),
    ('Cheque #DD Centex -47.01', 'Centex'),
]

for old, new in garbled_fixes:
    cur.execute("""
        UPDATE receipts 
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (new, old))
    count = cur.rowcount
    if count > 0:
        print(f'✅ Changed "{old}" → "{new}" ({count} rows)')
    else:
        print(f'⚠️  "{old}" not found')

print()

# Verify changes
print('STEP 4: Verification')
print('-'*80)

cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name LIKE '%LIQUOR%' OR vendor_name LIKE '%RED D%' OR vendor_name LIKE '%DRYDE%'
    GROUP BY vendor_name
""")

weird = cur.fetchall()
if weird:
    print('⚠️  Still found unusual vendor names:')
    for vendor, count in weird:
        print(f'  - {vendor} ({count} times)')
else:
    print('✅ No weird vendor names remain')

print()

conn.commit()
print('✅ All fixes completed')

cur.close()
conn.close()

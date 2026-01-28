#!/usr/bin/env python3
"""
Clean up CIBC banking account 0228362 descriptions:
1. Standardize Heffner Auto Finance (remove Lexus/Toyota suffixes)
2. Extract vendor from PRE-AUTH DEBIT → "LFG" (likely LFG Business PAD)
3. Extract vendor from Cheque #dd descriptions
4. Standardize Centex (remove extra suffixes)
5. Standardize Receiver General
6. Standardize Hertz
7. Standardize all liquor stores to just store name (no location details)
"""

import psycopg2
import re

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*80)
print('CLEANING UP CIBC BANKING ACCOUNT 0228362')
print('='*80)
print()

# Fix 1: Standardize Heffner entries
print('FIX 1: Heffner Auto Finance standardization')
print('-'*80)

# All Heffner cheques → "Heffner Auto Finance"
cur.execute("""
    UPDATE banking_transactions
    SET description = 'Heffner Auto Finance',
        vendor_extracted = 'Heffner Auto Finance'
    WHERE account_number = '0228362'
    AND (
        description LIKE 'Cheque %Heffner%Lexus%'
        OR description LIKE 'Cheque %Heffner%Toyota%'
        OR description LIKE 'Cheque %Heffner%:royota%'
    )
""")
heffner_cheques = cur.rowcount
print(f'✅ Standardized {heffner_cheques} Heffner cheque entries')

# Willie Heffner e-transfers → "Willie Heffner"
cur.execute("""
    UPDATE banking_transactions
    SET description = 'E-TRANSFER Willie Heffner',
        vendor_extracted = 'Willie Heffner'
    WHERE account_number = '0228362'
    AND description LIKE '%Heffner%'
    AND description LIKE '%E-TRANSFER%'
""")
heffner_etransfers = cur.rowcount
print(f'✅ Standardized {heffner_etransfers} Willie Heffner e-transfer entries')

# Heffner Auto Finance (already clean, just set vendor)
cur.execute("""
    UPDATE banking_transactions
    SET vendor_extracted = 'Heffner Auto Finance'
    WHERE account_number = '0228362'
    AND description = 'Heffner Auto Finance'
    AND (vendor_extracted IS NULL OR vendor_extracted = '')
""")
heffner_standard = cur.rowcount
print(f'✅ Set vendor for {heffner_standard} standard Heffner Auto Finance entries')

print()

# Fix 2: PRE-AUTH DEBIT LFG entries
print('FIX 2: PRE-AUTH DEBIT LFG Business PAD')
print('-'*80)

cur.execute("""
    UPDATE banking_transactions
    SET description = 'LFG Business PAD',
        vendor_extracted = 'LFG'
    WHERE account_number = '0228362'
    AND description LIKE 'PRE-AUTH DEBIT%LFG%'
""")
lfg_count = cur.rowcount
print(f'✅ Cleaned {lfg_count} PRE-AUTH DEBIT entries → "LFG Business PAD"')

print()

# Fix 3: Cheque #dd entries - extract vendor from description
print('FIX 3: Cheque #dd vendor extraction')
print('-'*80)

# Pattern: "Cheque #dd VendorName X" or "Cheque #dd VendorName -amount"
cur.execute("""
    SELECT transaction_id, description
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE 'Cheque %dd%' OR description LIKE 'Cheque %DD%')
""")

cheque_dd_rows = cur.fetchall()
cheque_dd_updated = 0

for tid, desc in cheque_dd_rows:
    # Extract vendor between "dd " and " X" or " -"
    match = re.search(r'#dd\s+([^X\-]+)', desc, re.IGNORECASE)
    if match:
        vendor = match.group(1).strip()
        # Remove trailing dots, colons, spaces
        vendor = re.sub(r'[\.:\s]+$', '', vendor)
        
        # Update to clean format
        cur.execute("""
            UPDATE banking_transactions
            SET description = %s,
                vendor_extracted = %s
            WHERE transaction_id = %s
        """, (f'Cheque {vendor}', vendor, tid))
        cheque_dd_updated += 1

print(f'✅ Extracted vendor from {cheque_dd_updated} Cheque #dd entries')

print()

# Fix 4: Centex standardization
print('FIX 4: Centex standardization')
print('-'*80)

cur.execute("""
    UPDATE banking_transactions
    SET description = 'Centex',
        vendor_extracted = 'Centex'
    WHERE account_number = '0228362'
    AND (
        description LIKE 'Centex%'
        OR description LIKE 'Cheque%Centex%'
    )
""")
centex_count = cur.rowcount
print(f'✅ Standardized {centex_count} Centex entries')

print()

# Fix 5: Receiver General standardization
print('FIX 5: Receiver General standardization')
print('-'*80)

cur.execute("""
    UPDATE banking_transactions
    SET description = 'Receiver General',
        vendor_extracted = 'Receiver General'
    WHERE account_number = '0228362'
    AND description LIKE '%Receiver%General%'
""")
receiver_count = cur.rowcount
print(f'✅ Standardized {receiver_count} Receiver General entries')

print()

# Fix 6: Hertz standardization
print('FIX 6: Hertz standardization')
print('-'*80)

cur.execute("""
    UPDATE banking_transactions
    SET description = 'Hertz',
        vendor_extracted = 'Hertz'
    WHERE account_number = '0228362'
    AND description LIKE '%Hertz%'
""")
hertz_count = cur.rowcount
print(f'✅ Standardized {hertz_count} Hertz entries')

print()

# Fix 7: Liquor stores - remove location details
print('FIX 7: Liquor store name standardization (remove locations)')
print('-'*80)

liquor_patterns = [
    ('LIQUOR BARN', '%LIQUOR BARN%', '%67%'),  # Already done, but catch any stragglers
    ('PLAZA LIQUOR', '%PLAZA LIQUOR%', None),
    ('LIQUOR DEPOT', '%LIQUOR DEPOT%', None),
    ('ONE STOP LIQUOR', '%ONE STOP LIQUOR%', None),
    ('SOBEYS LIQUOR', '%SOBEYS LIQUOR%', None),
    ('ACE LIQUOR', '%ACE LIQUOR%', None),
    ('SUPER LIQUOR', '%SUPER LIQUOR%', None),
    ('LIQUOR 7', '%LIQUOR 7%', None),
    ('GLOBAL LIQUOR', '%GLOBAL LIQUOR%', None),
    ('PLENTY OF LIQUOR', '%PLENTY OF LIQUOR%', None),
    ('LIQUOR MARKET', '%LIQUOR MARKET%', None),
    ('FILLCAN LIQUORS', '%FILLCAN LIQUOR%', None),
    ('WESTPARK LIQUOR', '%WESTPARK LIQUOR%', None),
    ('OLYMPIA LIQUOR', '%OLYMPIA LIQUOR%', None),
    ('URBAN LIQUOR', '%URBAN LIQUOR%', None),
    ('HOLIDAY LIQUOR', '%HOLIDAY LIQUOR%', None),
    ('LOCO LIQUOR', '%LOCO LIQUOR%', None),
    ('BROADWAY LIQUOR', '%BROADWAY LIQUOR%', None),
    ('BUYBUY LIQUOR', '%BUYBUY LIQUOR%', None),
    ('SOLO LIQUOR', '%SOLO LIQUOR%', None),
    ('UPTOWN LIQUOR', '%UPTOWN LIQUOR%', None),
]

total_liquor_fixed = 0
for vendor_name, pattern, exclude_pattern in liquor_patterns:
    if exclude_pattern:
        cur.execute(f"""
            UPDATE banking_transactions
            SET description = %s,
                vendor_extracted = %s
            WHERE account_number = '0228362'
            AND description LIKE %s
            AND description NOT LIKE %s
        """, (vendor_name, vendor_name, pattern, exclude_pattern))
    else:
        cur.execute(f"""
            UPDATE banking_transactions
            SET description = %s,
                vendor_extracted = %s
            WHERE account_number = '0228362'
            AND description LIKE %s
        """, (vendor_name, vendor_name, pattern))
    
    count = cur.rowcount
    if count > 0:
        print(f'  ✅ {vendor_name}: {count} entries')
        total_liquor_fixed += count

print(f'✅ Total liquor store entries standardized: {total_liquor_fixed}')

print()
print('='*80)
print('SUMMARY')
print('='*80)
print(f'Heffner cheques: {heffner_cheques}')
print(f'Willie Heffner e-transfers: {heffner_etransfers}')
print(f'Heffner Auto Finance (vendor set): {heffner_standard}')
print(f'LFG Business PAD: {lfg_count}')
print(f'Cheque #dd vendor extraction: {cheque_dd_updated}')
print(f'Centex: {centex_count}')
print(f'Receiver General: {receiver_count}')
print(f'Hertz: {hertz_count}')
print(f'Liquor stores: {total_liquor_fixed}')
print()

conn.commit()
print('✅ All changes committed')

cur.close()
conn.close()

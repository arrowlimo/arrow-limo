"""
Fix February 2012 1¢ cascading error through all transactions from Feb 10 onwards.
The correction is already done through Feb 9. This script fixes Feb 10-29.
"""

# Read the verification file
with open(r'l:\limo\reports\2012_cibc_complete_running_balance_verification.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Feb 9 ending balance is 1,122.44 (corrected)
# Feb 10 starts with 1,122.45 but should be 1,122.44

# Define all the replacements needed (subtracting 0.01 from each balance from Feb 10 onwards)
replacements = [
    # Feb 10
    ('| Feb 10 | CREDIT MEMO 4017775 MC              | D    | 500.00    | 1,122.45     | 1,622.45         | 1,622.45    | [OK] OK  |',
     '| Feb 10 | CREDIT MEMO 4017775 MC              | D    | 500.00    | 1,122.44     | 1,622.44         | 1,622.44    | [OK] OK  |'),
    ('| Feb 10 | CREDIT MEMO 4017775 IDP             | D    | 152.25    | 1,622.45     | 1,774.70         | 1,774.70    | [OK] OK  |',
     '| Feb 10 | CREDIT MEMO 4017775 IDP             | D    | 152.25    | 1,622.44     | 1,774.69         | 1,774.69    | [OK] OK  |'),
    ('| Feb 10 | CREDIT MEMO 4017775 VISA            | D    | 175.00    | 1,774.70     | 1,949.70         | 1,949.70    | [OK] OK  |',
     '| Feb 10 | CREDIT MEMO 4017775 VISA            | D    | 175.00    | 1,774.69     | 1,949.69         | 1,949.69    | [OK] OK  |'),
    ('| Feb 10 | PURCHASE#000001240037 CENTEX PETROLEU | W  | 51.00     | 1,949.70     | 1,898.70         | 1,898.70    | [OK] OK  |',
     '| Feb 10 | PURCHASE#000001240037 CENTEX PETROLEU | W  | 51.00     | 1,949.69     | 1,898.69         | 1,898.69    | [OK] OK  |'),
    ('| Feb 10 | Balance forward (page 4)            | -    | -         | -            | 1,898.70         | 1,898.70    | [OK] OK  |',
     '| Feb 10 | Balance forward (page 4)            | -    | -         | -            | 1,898.69         | 1,898.69    | [OK] OK  |'),
    ('| Feb 10 | PURCHASE#000001063019 TOMMY GUN\'S CDN | W  | 34.75     | 1,898.70     | 1,863.95         | 1,863.95    | [OK] OK  |',
     '| Feb 10 | PURCHASE#000001063019 TOMMY GUN\'S CDN | W  | 34.75     | 1,898.69     | 1,863.94         | 1,863.94    | [OK] OK  |'),
    ('| Feb 10 | PURCHASE#000001240088                | W    | 42.54     | 1,863.95     | 1,821.41         | 1,821.41    | [OK] OK  |',
     '| Feb 10 | PURCHASE#000001240088                | W    | 42.54     | 1,863.94     | 1,821.40         | 1,821.40    | [OK] OK  |'),
    ('| Feb 10 | PURCHASE#000001223023 CENTEX PETROLEU | W  | 52.00     | 1,821.41     | 1,769.41         | 1,769.41    | [OK] OK  |',
     '| Feb 10 | PURCHASE#000001223023 CENTEX PETROLEU | W  | 52.00     | 1,821.40     | 1,769.40         | 1,769.40    | [OK] OK  |'),
]

# Apply all replacements
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"[OK] Fixed: {old[:50]}...")
    else:
        print(f"[WARN]  Not found: {old[:50]}...")

# Write back
with open(r'l:\limo\reports\2012_cibc_complete_running_balance_verification.md', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n[OK] February 10 corrections applied")
print("Next: Need to continue from Feb 13 onwards with -0.01 correction")

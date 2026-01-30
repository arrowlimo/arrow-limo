import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== IMPLEMENTING NSF TRANSACTION COLOR CODING & PROPER CATEGORIZATION ===\n')

# Step 1: Check if display_color column exists
print('Step 1: Ensure display_color column exists in receipts...')
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
      AND column_name = 'display_color'
""")
if cur.fetchone():
    print('✅ display_color column exists\n')
else:
    print('  Adding display_color column...')
    cur.execute("""
        ALTER TABLE receipts 
        ADD COLUMN IF NOT EXISTS display_color VARCHAR(20)
    """)
    conn.commit()
    print('✅ Added display_color column\n')

# Step 2: Fix Receipt 142874 - The ACTUAL NSF Fee (YELLOW)
print('Step 2: Correcting Receipt 142874 (Actual NSF Fee)...')
cur.execute("""
    UPDATE receipts
    SET vendor_name = 'CIBC NSF FEE',
        canonical_vendor = 'CIBC',
        category = 'Bank Charges',
        sub_classification = 'NSF Fees',
        display_color = 'yellow',
        description = 'Bank charged NSF fee'
    WHERE receipt_id = 142874
""")
conn.commit()
print('✅ Receipt 142874: CIBC NSF FEE (YELLOW - bank expense)\n')

# Step 3: Fix Receipt 142875 - The NSF Fee REVERSAL/CREDIT (GREEN)
print('Step 3: Correcting Receipt 142875 (NSF Fee Reversal)...')
cur.execute("""
    UPDATE receipts
    SET vendor_name = 'CIBC NSF FEE REVERSAL',
        canonical_vendor = 'CIBC',
        category = 'Bank Charges',
        sub_classification = 'Fee Reversals',
        display_color = 'green',
        description = 'Bank reversed/credited back NSF fee',
        gross_amount = -135.00  -- Make it negative to show credit
    WHERE receipt_id = 142875
""")
conn.commit()
print('✅ Receipt 142875: CIBC NSF FEE REVERSAL (GREEN - credit back)\n')

# Step 4: Color code NSF returns (bounced customer payments) as RED
print('Step 4: Color coding NSF returns (bounced cheques) as RED...')
cur.execute("""
    UPDATE receipts
    SET display_color = 'red',
        category = 'NSF Returns',
        sub_classification = 'Bad Cheques'
    WHERE (UPPER(vendor_name) LIKE '%NSF%' OR UPPER(description) LIKE '%NSF%')
      AND vendor_name NOT LIKE '%FEE%'
      AND vendor_name NOT LIKE '%REVERSAL%'
      AND vendor_name NOT LIKE '%CHARGE%'
      AND receipt_id != 142874
      AND receipt_id != 142875
      AND is_nsf = TRUE
""")
nsf_returns = cur.rowcount
conn.commit()
print(f'✅ Marked {nsf_returns} NSF returns as RED\n')

# Step 5: Summary of the color coding system
print('='*80)
print('NSF TRANSACTION COLOR CODING SUMMARY')
print('='*80 + '\n')

cur.execute("""
    SELECT display_color, COUNT(*), 
           STRING_AGG(DISTINCT category, ', ') as categories
    FROM receipts
    WHERE display_color IN ('red', 'yellow', 'green')
       OR (UPPER(vendor_name) LIKE '%NSF%' OR UPPER(description) LIKE '%NSF%')
    GROUP BY display_color
    ORDER BY display_color NULLS LAST
""")
summary = cur.fetchall()

color_meanings = {
    'red': 'NSF Returns (customer payments that bounced)',
    'yellow': 'NSF Fees (bank charges to us)',
    'green': 'NSF Reversals (bank credits/corrections)',
    None: 'Not yet categorized'
}

for row in summary:
    color = row[0] or 'none'
    count = row[1]
    categories = row[2] or 'various'
    meaning = color_meanings.get(row[0], 'Unknown')
    print(f'{color.upper():10} | {count:4} receipts | {meaning}')
    print(f'           | Categories: {categories}\n')

print('\n' + '='*80)
print('VERIFICATION - Sept 17, 2012 NSF Transactions')
print('='*80 + '\n')

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, display_color, category
    FROM receipts
    WHERE receipt_date = '2012-09-17'
      AND (UPPER(vendor_name) LIKE '%NSF%' 
           OR UPPER(vendor_name) LIKE '%BANK FEE%'
           OR receipt_id IN (142874, 142875))
    ORDER BY receipt_id
""")
sept17 = cur.fetchall()
for r in sept17:
    color_emoji = '🔴' if r[3] == 'red' else '🟡' if r[3] == 'yellow' else '🟢' if r[3] == 'green' else '⚪'
    print(f'{color_emoji} Receipt {r[0]:6} | {r[1]:30} | ${r[2]:8.2f} | {r[3] or "none":8} | {r[4] or "none"}')

conn.close()

print('\n✅ NSF transaction categorization and color coding complete!')

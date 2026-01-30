import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== CORRECTING NSF CATEGORIZATION - Business Check Bounces ===\n')
print('These are ARROW LIMOUSINE checks that bounced (insufficient funds)')
print('NOT customer payments that bounced\n')

# Check all NSF returns on Sept 17, 2012
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, 
           bt.description, bt.debit_amount, bt.credit_amount
    FROM receipts r 
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.receipt_date = '2012-09-17'
      AND (UPPER(bt.description) LIKE '%NSF%' 
           OR UPPER(bt.description) LIKE '%JACK CARTER%'
           OR UPPER(bt.description) LIKE '%OPTIMUM%')
      AND r.receipt_id != 142874  -- Exclude the NSF fee itself
      AND r.receipt_id != 142875  -- Exclude the fee reversal
    ORDER BY r.receipt_id
""")
bounced_checks = cur.fetchall()

print(f'Found {len(bounced_checks)} bounced business checks:\n')
for bc in bounced_checks:
    print(f'  Receipt {bc[0]}: {bc[1][:40]:40} ${bc[2]:9.2f} | {bc[3]}')

print('\n' + '='*80)
print('CORRECTED CATEGORIZATION')
print('='*80 + '\n')

# Update Jack Carter NSF - this is Arrow Limo's check that bounced
print('Updating Receipt 142869 (Jack Carter)...')
cur.execute("""
    UPDATE receipts
    SET vendor_name = 'JACK CARTER',
        canonical_vendor = 'JACK CARTER',
        category = 'NSF - Business Checks',
        sub_classification = 'Insufficient Funds',
        display_color = 'orange',
        description = 'Arrow Limo check bounced - insufficient funds',
        is_nsf = TRUE
    WHERE receipt_id = 142869
""")
conn.commit()
print('✅ Receipt 142869: JACK CARTER (ORANGE - business check bounced)\n')

# Check for Optimum West Insurance and other bounced checks
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, bt.description
    FROM receipts r 
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.receipt_date = '2012-09-17'
      AND UPPER(bt.description) LIKE '%OPTIMUM%'
""")
optimum = cur.fetchall()

if optimum:
    print('Found Optimum West Insurance transactions:')
    for o in optimum:
        print(f'  Receipt {o[0]}: {o[1]} | {o[2]}')
        
    # Update any Optimum West NSF
    cur.execute("""
        UPDATE receipts
        SET category = 'NSF - Business Checks',
            sub_classification = 'Insufficient Funds',
            display_color = 'orange',
            description = 'Arrow Limo check bounced - insufficient funds',
            is_nsf = TRUE
        WHERE receipt_id IN (
            SELECT r.receipt_id
            FROM receipts r 
            JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
            WHERE r.receipt_date = '2012-09-17'
              AND UPPER(bt.description) LIKE '%OPTIMUM%'
              AND UPPER(bt.description) LIKE '%NSF%'
        )
    """)
    updated = cur.rowcount
    conn.commit()
    print(f'✅ Updated {updated} Optimum West NSF receipts\n')

print('='*80)
print('REVISED COLOR CODE SYSTEM')
print('='*80 + '\n')
print('🔴 RED    = Customer payments that bounced (customer NSF - revenue lost)')
print('🟠 ORANGE = Business checks that bounced (cash flow problem - insufficient funds)')
print('🟡 YELLOW = Bank fees/charges (normal banking expenses)')
print('🟢 GREEN  = Credits/reversals (money back to us)')
print('⚪ GRAY   = Neutral/offsetting entries')
print('\n')

print('='*80)
print('FINAL CATEGORIZATION - Sept 17, 2012')
print('='*80 + '\n')

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, display_color, category, sub_classification
    FROM receipts
    WHERE receipt_date = '2012-09-17'
      AND (UPPER(vendor_name) LIKE '%NSF%' 
           OR UPPER(vendor_name) LIKE '%BANK FEE%'
           OR UPPER(vendor_name) LIKE '%JACK CARTER%'
           OR UPPER(vendor_name) LIKE '%OPTIMUM%'
           OR display_color IN ('red', 'orange', 'yellow', 'green'))
    ORDER BY receipt_id
""")

for row in cur.fetchall():
    color_emoji = '🔴' if row[3] == 'red' else '🟠' if row[3] == 'orange' else '🟡' if row[3] == 'yellow' else '🟢' if row[3] == 'green' else '⚪'
    print(f'{color_emoji} {row[0]:6} | {row[1][:40]:40} | ${row[2]:9.2f} | {row[4] or "none":25} | {row[5] or "none"}')

print('\n📊 BUSINESS IMPACT:')
print('The bounced checks indicate Arrow Limousine had cash flow issues in Sept 2012')
print('Payments to vendors (Jack Carter, Optimum West) were returned due to insufficient funds')

conn.close()

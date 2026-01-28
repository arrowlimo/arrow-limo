import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('Updating Optimum West Insurance NSF receipt...\n')

cur.execute("""
    UPDATE receipts 
    SET vendor_name = 'OPTIMUM WEST INSURANCE',
        canonical_vendor = 'OPTIMUM WEST INSURANCE',
        category = 'NSF - Business Checks',
        sub_classification = 'Insufficient Funds',
        display_color = 'orange',
        description = 'Arrow Limo check bounced - insufficient funds',
        is_nsf = TRUE 
    WHERE receipt_id = 142868
""")
conn.commit()
print(f'✅ Updated receipt 142868: {cur.rowcount} row\n')

print('='*80)
print('COMPLETE NSF TRANSACTION SUMMARY - September 17, 2012')
print('='*80 + '\n')

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, display_color, 
           category, sub_classification, description
    FROM receipts
    WHERE receipt_date = '2012-09-17'
      AND (display_color IN ('orange', 'yellow', 'green')
           OR UPPER(vendor_name) LIKE '%NSF%'
           OR UPPER(vendor_name) LIKE '%OPTIMUM%'
           OR UPPER(vendor_name) LIKE '%JACK CARTER%')
    ORDER BY 
        CASE display_color
            WHEN 'orange' THEN 1
            WHEN 'yellow' THEN 2
            WHEN 'green' THEN 3
            ELSE 4
        END,
        receipt_id
""")

total_bounced = 0
total_fees = 0
total_credits = 0

for row in cur.fetchall():
    color_emoji = '🟠' if row[3] == 'orange' else '🟡' if row[3] == 'yellow' else '🟢' if row[3] == 'green' else '⚪'
    print(f'{color_emoji} Receipt {row[0]:6} | {row[1][:35]:35} | ${row[2]:9.2f}')
    print(f'   Category: {row[4]} / {row[5] or "none"}')
    print(f'   Note: {row[6] or "none"}\n')
    
    if row[3] == 'orange':
        total_bounced += row[2]
    elif row[3] == 'yellow':
        total_fees += row[2]
    elif row[3] == 'green':
        total_credits += row[2]

print('='*80)
print('FINANCIAL IMPACT SUMMARY')
print('='*80)
print(f'🟠 Business checks bounced (insufficient funds): ${total_bounced:10.2f}')
print(f'🟡 Bank NSF fees charged:                        ${total_fees:10.2f}')
print(f'🟢 Bank fee credits/reversals:                   ${total_credits:10.2f}')
print(f'   {"─"*58}')
print(f'   Net NSF fees paid:                            ${total_fees + total_credits:10.2f}')
print(f'   Total cash flow impact:                       ${total_bounced + total_fees + total_credits:10.2f}')
print('\n📊 Analysis: Arrow Limousine had insufficient funds on Sept 17, 2012')
print(f'   - Checks to vendors bounced (${total_bounced:.2f})')
print(f'   - Bank charged NSF fee but then reversed it (net ${total_fees + total_credits:.2f})')

conn.close()

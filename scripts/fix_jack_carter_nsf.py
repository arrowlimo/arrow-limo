import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== Analyzing and Fixing Receipt 142869 (Jack Carter NSF) ===\n')

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.display_color,
           bt.description, bt.debit_amount, bt.credit_amount
    FROM receipts r 
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.receipt_id = 142869
""")
r = cur.fetchone()

print(f'Current Receipt:')
print(f'  ID: {r[0]}')
print(f'  Vendor: {r[1]}')
print(f'  Amount: ${r[2]:.2f}')
print(f'  Color: {r[3] or "none"}')
print(f'\nBanking Transaction:')
print(f'  Description: {r[4]}')
print(f'  Debit: ${r[5]:.2f}' if r[5] else '  Debit: None')
print(f'  Credit: ${r[6]:.2f}' if r[6] else '  Credit: None')

# This is a DEBIT for NSF - meaning a customer payment bounced
# Should be RED (customer's bad cheque)
print(f'\n>>> This is a customer payment that BOUNCED (Jack Carter)')
print(f'>>> Should be RED (nsf_return)\n')

cur.execute("""
    UPDATE receipts
    SET vendor_name = 'JACK CARTER - NSF RETURN',
        canonical_vendor = 'JACK CARTER',
        category = 'NSF Returns',
        sub_classification = 'Bad Cheques',
        display_color = 'red',
        description = 'Customer payment bounced - NSF',
        is_nsf = TRUE
    WHERE receipt_id = 142869
""")
conn.commit()
print('✅ Updated receipt 142869 to RED (customer NSF return)\n')

# Now show final categorization
print('='*80)
print('FINAL NSF CATEGORIZATION for Sept 17, 2012')
print('='*80 + '\n')

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, display_color, category, sub_classification
    FROM receipts
    WHERE receipt_date = '2012-09-17'
      AND (UPPER(vendor_name) LIKE '%NSF%' 
           OR UPPER(vendor_name) LIKE '%BANK FEE%'
           OR UPPER(vendor_name) LIKE '%JACK CARTER%')
    ORDER BY receipt_id
""")

for row in cur.fetchall():
    color_emoji = '🔴' if row[3] == 'red' else '🟡' if row[3] == 'yellow' else '🟢' if row[3] == 'green' else '⚪'
    print(f'{color_emoji} {row[0]:6} | {row[1][:35]:35} | ${row[2]:9.2f} | {row[4] or "none":20} | {row[5] or "none"}')

print('\n' + '='*80)
print('COLOR CODE MEANINGS')
print('='*80)
print('🔴 RED    = Customer payment bounced (their bad cheque - we lose money)')
print('🟡 YELLOW = Bank charged us an NSF fee (our expense)')
print('🟢 GREEN  = Bank reversed/credited the fee back (money back to us)')
print('='*80)

conn.close()

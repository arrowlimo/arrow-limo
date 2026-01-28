import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=== DETAILED NSF TRANSACTION ANALYSIS for Sept 17, 2012 ===\n')

# Check the two receipts in question
receipt_ids = [142874, 142875]

for rid in receipt_ids:
    print(f'\n{"="*80}')
    print(f'RECEIPT {rid}')
    print("="*80)
    
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               banking_transaction_id, description, payment_method
        FROM receipts 
        WHERE receipt_id = %s
    """, (rid,))
    r = cur.fetchone()
    
    if r:
        print(f'\nReceipt Details:')
        print(f'  Date: {r[1]}')
        print(f'  Vendor: {r[2]}')
        print(f'  Amount: ${r[3]:.2f}')
        print(f'  Banking ID: {r[4]}')
        print(f'  Description: {r[5] or "none"}')
        print(f'  Payment Method: {r[6] or "none"}')
        
        # Get banking transaction details
        if r[4]:
            cur.execute("""
                SELECT transaction_id, transaction_date, description, 
                       debit_amount, credit_amount, account_number, category
                FROM banking_transactions 
                WHERE transaction_id = %s
            """, (r[4],))
            b = cur.fetchone()
            if b:
                print(f'\nBanking Transaction:')
                print(f'  ID: {b[0]}')
                print(f'  Date: {b[1]}')
                print(f'  Description: {b[2]}')
                print(f'  Debit Amount: ${b[3]:.2f}' if b[3] else f'  Debit Amount: None')
                print(f'  Credit Amount: ${b[4]:.2f}' if b[4] else f'  Credit Amount: None')
                print(f'  Account: {b[5]}')
                print(f'  Category: {b[6] or "none"}')
                
                # Determine the nature
                if b[3] and b[3] > 0:  # Debit (money out)
                    print(f'\n  >>> TYPE: EXPENSE (money OUT of account)')
                    print(f'  >>> This is the ACTUAL NSF FEE charged by the bank')
                elif b[4] and b[4] > 0:  # Credit (money in)
                    print(f'\n  >>> TYPE: REVERSAL/CREDIT (money INTO account)')
                    print(f'  >>> This is the bank REVERSING/CREDITING BACK the NSF fee')

print('\n\n' + '='*80)
print('RECOMMENDED CORRECTIONS')
print('='*80 + '\n')

print('Receipt 142874 (Banking 57832):')
print('  Current: vendor_name = "NSF FEE"')
print('  Should be: vendor_name = "CIBC NSF FEE" (actual bank charge)')
print('  Category: Bank Charges / NSF Fees')
print('  Color: YELLOW (banking fee - legitimate expense)')
print('')

print('Receipt 142875 (Banking 81063):')
print('  Current: vendor_name = "BANK FEE"')
print('  Should be: vendor_name = "CIBC NSF FEE REVERSAL" or "NSF FEE CREDIT"')
print('  Category: Bank Charges / Fee Reversals')
print('  Color: GREEN (credit/reversal - money back)')
print('')

print('For NSF-RELATED items (bounced cheques):')
print('  Examples: "Jack Carter (NSF)", "Optimum West Insurance (NSF)"')
print('  Category: NSF Returns / Bad Cheques')
print('  Color: RED (problematic transaction - customer payment failed)')
print('')

print('='*80)
print('PROPOSED COLOR CODING SYSTEM')
print('='*80 + '\n')
print('RED (nsf_return):')
print('  - Customer payment that bounced (NSF)')
print('  - Reversed deposits')
print('  - Bad cheques')
print('')
print('YELLOW (nsf_fee):')
print('  - Bank NSF fees charged to us')
print('  - Other bank service charges')
print('  - Legitimate operating expense')
print('')
print('GREEN (nsf_reversal):')
print('  - Bank fee reversals/credits')
print('  - Corrections in our favor')
print('  - Money coming back to us')
print('')
print('GRAY (nsf_related):')
print('  - Corrections that net to zero')
print('  - Offsetting entries')

conn.close()

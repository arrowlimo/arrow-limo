import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=== ALL $135.00 RECEIPTS on 2012-09-17 ===\n')

receipt_ids = [138832, 140659, 142874, 142875]

for rid in receipt_ids:
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id
        FROM receipts 
        WHERE receipt_id = %s
    """, (rid,))
    r = cur.fetchone()
    if r:
        print(f'Receipt ID: {r[0]:6} | Vendor: {r[1][:30]:30} | Amount: ${r[2]:7.2f}')
        
        # Get banking details
        if r[3]:
            cur.execute("""
                SELECT transaction_id, description, account_number, bank_id, 
                       debit_amount, credit_amount
                FROM banking_transactions 
                WHERE transaction_id = %s
            """, (r[3],))
            b = cur.fetchone()
            if b:
                amt = b[4] if b[4] else -b[5]
                bank = "CIBC 0228362" if b[3] == 1 else "Scotia 903990106011" if b[3] == 2 else f"Journal Account {b[2]}"
                print(f'  Banking: ID {b[0]:5} | {bank:25} | ${amt:8.2f} | {b[1]}')
        print()

print('\n=== ANALYSIS ===\n')
print('1. Receipt 140659 = FISHER ST STATION ON (Shell gas)')
print('   - Banking 69333 from Scotia account')
print('   - LEGITIMATE EXPENSE\n')

print('2. Receipt 142874 = NSF FEE')
print('   - Banking 57832 from CIBC account')
print('   - CIBC charged a $135 NSF fee (DEBIT)\n')

print('3. Receipt 142875 = BANK FEE')
print('   - Banking 81063 from CIBC account')
print('   - Description: "Cheque Expense - Bank Charges & Interest"')
print('   - This appears to be a CREDIT (-$135) - likely a reversal/correction\n')

print('4. Receipt 138832 = NSF CHARGE')
print('   - Banking 82299 from Journal Account 1615')
print('   - This is NOT a real bank account - it\'s a manual journal entry')
print('   - This is likely a DUPLICATE of the CIBC NSF fee (double-entry)\n')

print('CONCLUSION:')
print('- Receipt 142875 (BANK FEE -$135) looks like a CREDIT/REVERSAL of the NSF fee')
print('- Receipt 138832 (NSF CHARGE from account 1615) is a DUPLICATE journal entry')
print('- Only ONE real NSF fee was charged: Receipt 142874 ($135 from CIBC)')

conn.close()

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=== RECEIPT 138532 DETAILS ===\n')
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           banking_transaction_id, description, source_system
    FROM receipts 
    WHERE receipt_id = 138532
""")
r = cur.fetchone()
if r:
    print(f'Receipt ID: {r[0]}')
    print(f'Date: {r[1]}')
    print(f'Vendor: {r[2]}')
    print(f'Amount: ${r[3]:.2f}')
    print(f'Banking ID: {r[4]}')
    print(f'Description: {r[5] or "none"}')
    print(f'Source System: {r[6]}')

print('\n=== BANKING TRANSACTION 82299 ===')
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount, account_number, bank_id, source_file
    FROM banking_transactions 
    WHERE transaction_id = 82299
""")
b = cur.fetchone()
if b:
    amt = b[3] if b[3] else -b[4]
    print(f'Transaction ID: {b[0]}')
    print(f'Date: {b[1]}')
    print(f'Description: {b[2]}')
    print(f'Amount: ${amt:.2f}')
    print(f'Account: {b[5]}')
    print(f'Bank ID: {b[6]}')
    print(f'Source File: {b[7] or "NOT SET"}')

print('\n=== THE FULL NSF STORY on Sept 17, 2012 ===\n')
print('Looking at ALL transactions related to NSF on this date...\n')

cur.execute("""
    SELECT transaction_id, account_number, description, 
           debit_amount, credit_amount, bank_id
    FROM banking_transactions 
    WHERE transaction_date = '2012-09-17'
      AND (UPPER(description) LIKE '%NSF%' 
           OR UPPER(description) LIKE '%JACK CARTER%'
           OR UPPER(description) LIKE '%OPTIMUM%'
           OR UPPER(description) LIKE '%CORRECTION%'
           OR UPPER(description) LIKE '%LFG%')
    ORDER BY transaction_id
""")
all_nsf = cur.fetchall()
print(f'Total NSF-related transactions: {len(all_nsf)}\n')
for t in all_nsf:
    amt = t[3] if t[3] else -t[4]
    acct_name = "CIBC" if t[5] == 1 else "Scotia" if t[5] == 2 else "Journal"
    print(f'{t[0]:5} | {acct_name:8} | {t[1]:15} | ${amt:9.2f} | {t[2]}')

print('\n=== SUMMARY ===')
print('Account 1615 is likely a journal/manual entry account (not a real bank account)')
print('CIBC 0228362 charged the actual NSF fee')
print('Transaction 81063 appears to be a correction/reversal (credit back)')

conn.close()

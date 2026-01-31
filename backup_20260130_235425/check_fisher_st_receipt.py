import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== RECEIPT LINKED TO BANKING 69333 (FISHER ST STATION) ===')
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, 
           gross_amount, payment_method, canonical_pay_method, 
           banking_transaction_id, description
    FROM receipts 
    WHERE banking_transaction_id = 69333
""")
r = cur.fetchone()
if r:
    print(f'Receipt ID: {r[0]}')
    print(f'Date: {r[1]}')
    print(f'Vendor Name: {r[2]}')
    print(f'Canonical Vendor: {r[3] or "NOT SET"}')
    print(f'Amount: ${r[4]:.2f}')
    print(f'Payment Method: {r[5] or "NOT SET"}')
    print(f'Canonical Pay Method: {r[6] or "NOT SET"}')
    print(f'Banking ID: {r[7]}')
    print(f'Description: {r[8] or "none"}')
else:
    print('No receipt found linked to banking transaction 69333')

print('\n=== BANKING TRANSACTION 69333 ===')
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, 
           account_number, vendor_extracted
    FROM banking_transactions 
    WHERE transaction_id = 69333
""")
b = cur.fetchone()
if b:
    amt = b[2] if b[2] else -b[3]
    print(f'Date: {b[0]}')
    print(f'Description: {b[1]}')
    print(f'Amount: ${amt:.2f}')
    print(f'Account: {b[4]}')
    print(f'Vendor Extracted: {b[5] or "NOT SET"}')

conn.close()

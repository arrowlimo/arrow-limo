import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

receipt_ids = [142375, 142874, 138532]  # The three NSF-related receipts

print('=== NSF CHARGES - RECEIPT DETAILS ===\n')
for rid in receipt_ids:
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               banking_transaction_id, description, canonical_vendor
        FROM receipts 
        WHERE receipt_id = %s
    """, (rid,))
    r = cur.fetchone()
    if r:
        print(f'Receipt ID: {r[0]}')
        print(f'  Date: {r[1]}')
        print(f'  Vendor: {r[2]}')
        print(f'  Amount: ${r[3]:.2f}')
        print(f'  Banking ID: {r[4]}')
        print(f'  Description: {r[5] or "none"}')
        print(f'  Canonical Vendor: {r[6] or "NOT SET"}')
        
        # Get banking transaction details
        if r[4]:
            cur.execute("""
                SELECT transaction_id, transaction_date, description, 
                       debit_amount, credit_amount, account_number, bank_id
                FROM banking_transactions 
                WHERE transaction_id = %s
            """, (r[4],))
            b = cur.fetchone()
            if b:
                amt = b[3] if b[3] else -b[4]
                bank_name = "CIBC 0228362" if b[6] == 1 else "Scotia 903990106011" if b[6] == 2 else f"Account 1615" if b[5] == '1615' else f"Unknown (bank_id={b[6]})"
                print(f'  Banking Transaction:')
                print(f'    ID: {b[0]}')
                print(f'    Date: {b[1]}')
                print(f'    Description: {b[2]}')
                print(f'    Amount: ${amt:.2f}')
                print(f'    Account: {b[5]} ({bank_name})')
        print()

print('\n=== ALL BANKING TRANSACTIONS for $135 NSF on 2012-09-17 ===\n')
cur.execute("""
    SELECT transaction_id, description, account_number, bank_id, 
           debit_amount, credit_amount, category
    FROM banking_transactions 
    WHERE transaction_date = '2012-09-17'
      AND (UPPER(description) LIKE '%NSF%' 
           OR UPPER(description) LIKE '%BANK CHARGE%'
           OR UPPER(description) LIKE '%CHEQUE EXPENSE%')
      AND (debit_amount = 135.00 OR credit_amount = 135.00 OR debit_amount = -135.00 OR credit_amount = -135.00)
    ORDER BY transaction_id
""")
nsf_transactions = cur.fetchall()
for b in nsf_transactions:
    amt = b[4] if b[4] else -b[5]
    bank_name = "CIBC" if b[3] == 1 else "Scotia" if b[3] == 2 else "Journal/Manual"
    print(f'Transaction ID: {b[0]} | {bank_name:15} | Account: {b[2]:15} | ${amt:8.2f} | {b[1]}')

conn.close()

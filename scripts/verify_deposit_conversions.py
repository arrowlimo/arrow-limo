#!/usr/bin/env python3
"""
Verify the actual content of suspicious DEPOSIT variations
Check descriptions, amounts, and linked banking info
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get details for the suspicious deposits we just changed
suspicious_vendors = [
    'DEPOSIT FROM IFS',
    'DEPOSIT FROM CAMBRIDE ON',
]

print("VERIFICATION OF CONVERTED DEPOSITS")
print("=" * 120)

for vendor in suspicious_vendors:
    print(f"\n\nVENDOR: {vendor}")
    print("=" * 120)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.vendor_name,
            r.gross_amount,
            r.description,
            r.receipt_date,
            bt.description as banking_desc,
            bt.debit_amount,
            bt.credit_amount,
            bt.transaction_date
        FROM receipts r
        LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.vendor_name = %s
        ORDER BY r.receipt_date DESC
    """, (vendor,))
    
    rows = cur.fetchall()
    if not rows:
        print(f"No receipts found with vendor_name = {vendor}")
        continue
    
    for receipt_id, curr_vendor, amount, desc, date, bank_desc, debit, credit, bank_date in rows:
        print(f"\nReceipt ID: {receipt_id}")
        print(f"Date: {date}")
        print(f"Receipt Amount: ${amount:.2f if amount else 'NULL'}")
        print(f"Description: {desc}")
        if bank_desc:
            print(f"Banking Description: {bank_desc}")
            print(f"Banking Debit: ${debit:.2f if debit else '0'} | Credit: ${credit:.2f if credit else '0'}")
            print(f"Banking Date: {bank_date}")

cur.close()
conn.close()

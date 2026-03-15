"""
Create receipt for Cheque #61 - PAUL RICHARD paycheck
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("=" * 100)
print("CREATE RECEIPT FOR CHEQUE #61 - PAUL RICHARD PAYCHECK")
print("=" * 100)

# Insert the receipt
receipt_data = {
    'receipt_date': '2012-10-01',
    'vendor_name': 'CHQ 61 PAUL RICHARD',
    'gross_amount': 2200.00,
    'gst_amount': 0.00,  # Paychecks don't have GST
    'description': 'Paycheck - Driver Pay',
    'category': 'Driver & Payroll Expenses',
    'gl_account_code': '5210',  # Driver Wages GL code
    'payment_method': 'cheque',
    'banking_transaction_id': 69394,
    'created_at': datetime.now()
}

cur.execute("""
    INSERT INTO receipts (
        receipt_date,
        vendor_name,
        gross_amount,
        gst_amount,
        description,
        category,
        gl_account_code,
        payment_method,
        banking_transaction_id,
        created_at
    ) VALUES (
        %(receipt_date)s,
        %(vendor_name)s,
        %(gross_amount)s,
        %(gst_amount)s,
        %(description)s,
        %(category)s,
        %(gl_account_code)s,
        %(payment_method)s,
        %(banking_transaction_id)s,
        %(created_at)s
    )
    RETURNING receipt_id
""", receipt_data)

receipt_id = cur.fetchone()[0]
conn.commit()

print(f"\n[OK] Created receipt #{receipt_id}")
print(f"  Date: {receipt_data['receipt_date']}")
print(f"  Vendor: {receipt_data['vendor_name']}")
print(f"  Amount: ${receipt_data['gross_amount']:,.2f}")
print(f"  Category: {receipt_data['category']}")
print(f"  GL Code: {receipt_data['gl_account_code']}")
print(f"  Description: {receipt_data['description']}")
print(f"  Linked to Banking Transaction: {receipt_data['banking_transaction_id']}")

# Verify the link
cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        r.gross_amount,
        bt.transaction_id,
        bt.description,
        bt.debit_amount
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.receipt_id = %s
""", (receipt_id,))

result = cur.fetchone()
if result:
    rec_id, vendor, rec_amt, trans_id, trans_desc, bank_amt = result
    print("\n[OK] Verified link:")
    print(f"  Receipt #{rec_id}: {vendor} ${rec_amt:,.2f}")
    print(f"  Banking #{trans_id}: {trans_desc} ${bank_amt:,.2f}")
    print(f"  Match: {'YES' if abs(rec_amt - bank_amt) < 0.01 else 'NO'}")

conn.close()

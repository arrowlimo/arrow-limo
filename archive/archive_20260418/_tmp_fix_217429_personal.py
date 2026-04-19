import psycopg2
from decimal import Decimal

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
conn.autocommit = False

cur.execute("""
    UPDATE receipts SET
        is_personal_purchase  = TRUE,
        owner_personal_amount = 181.00,
        business_personal     = 'Personal',
        updated_at            = NOW()
    WHERE receipt_id = 217429
""")
print('Updated 217429 personal flags:', cur.rowcount)

cur.execute("""SELECT receipt_id, vendor_name, gross_amount, description,
               is_personal_purchase, owner_personal_amount, business_personal,
               banking_transaction_id
               FROM receipts WHERE banking_transaction_id = 102214 ORDER BY receipt_id""")
cols = [d[0] for d in cur.description]
total = Decimal('0')
for row in cur.fetchall():
    d = dict(zip(cols, row))
    marker = '(PERSONAL)' if d['is_personal_purchase'] else ''
    print(f"  {d['receipt_id']}  {d['vendor_name']}  ${d['gross_amount']}  {d['description']}  {marker}")
    total += d['gross_amount']
print(f"  Total: ${total}  BT debit: $374.96  Match: {total == Decimal('374.96')}")

conn.commit()
print('Committed.')
conn.close()

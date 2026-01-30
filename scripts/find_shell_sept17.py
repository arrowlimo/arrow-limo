import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== SHELL RECEIPTS on 2012-09-17 ===')
cur.execute("""
    SELECT receipt_date, vendor_name, canonical_vendor, gross_amount, 
           payment_method, canonical_pay_method, description, 
           banking_transaction_id, receipt_id
    FROM receipts 
    WHERE receipt_date = '2012-09-17' 
      AND (UPPER(vendor_name) LIKE '%SHELL%' 
           OR UPPER(canonical_vendor) LIKE '%SHELL%' 
           OR UPPER(description) LIKE '%SHELL%')
    ORDER BY receipt_id
""")
rows = cur.fetchall()
print(f'\nTotal Shell receipts on 2012-09-17: {len(rows)}')
for r in rows:
    print(f'{r[0]} | Vendor:{r[1][:25]:25} | Can:{r[2] or "none":20} | ${r[3]:7.2f}')
    print(f'  PayMethod:{r[4] or "none":15} | CanPay:{r[5] or "none":15} | Banking:{r[7] or "NOT LINKED"} | RID:{r[8]}')
    print(f'  Description: {r[6] or "none"}')
    print()

print('\n=== ALL SHELL RECEIPTS in September 2012 ===')
cur.execute("""
    SELECT receipt_date, vendor_name, canonical_vendor, gross_amount, 
           canonical_pay_method, banking_transaction_id, receipt_id
    FROM receipts 
    WHERE receipt_date BETWEEN '2012-09-01' AND '2012-09-30'
      AND (UPPER(vendor_name) LIKE '%SHELL%' 
           OR UPPER(canonical_vendor) LIKE '%SHELL%')
    ORDER BY receipt_date
""")
rows = cur.fetchall()
print(f'\nTotal Shell receipts in September 2012: {len(rows)}')
for r in rows:
    banking_status = "BANKED" if r[5] else "CASH/NOT LINKED"
    print(f'{r[0]} | {r[1][:30]:30} | ${r[3]:7.2f} | {r[4] or "unknown":15} | {banking_status:15} | RID:{r[6]}')

conn.close()

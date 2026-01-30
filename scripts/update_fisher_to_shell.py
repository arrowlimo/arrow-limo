import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== UPDATING RECEIPT 140659 ===')
cur.execute("""
    UPDATE receipts 
    SET canonical_vendor = %s
    WHERE receipt_id = %s
""", ('SHELL', 140659))
conn.commit()

print(f'✅ Updated receipt 140659: canonical_vendor set to SHELL')
print(f'Rows affected: {cur.rowcount}')

# Verify the update
cur.execute("""
    SELECT receipt_id, vendor_name, canonical_vendor, gross_amount, banking_transaction_id
    FROM receipts 
    WHERE receipt_id = 140659
""")
r = cur.fetchone()
print(f'\nVerified:')
print(f'  Receipt ID: {r[0]}')
print(f'  Vendor Name: {r[1]}')
print(f'  Canonical Vendor: {r[2]}')
print(f'  Amount: ${r[3]:.2f}')
print(f'  Banking Transaction ID: {r[4]}')

# Also update the banking transaction vendor_extracted
print('\n=== UPDATING BANKING TRANSACTION 69333 ===')
cur.execute("""
    UPDATE banking_transactions
    SET vendor_extracted = %s
    WHERE transaction_id = %s
""", ('SHELL', 69333))
conn.commit()
print(f'✅ Updated banking transaction 69333: vendor_extracted set to SHELL')
print(f'Rows affected: {cur.rowcount}')

conn.close()

print('\n✅ SUCCESS: FISHER ST STATION is now searchable as SHELL')
print('The receipt will now appear in banking lookup searches for "Shell"')

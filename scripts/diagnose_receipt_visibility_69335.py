import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('Receipts linked to banking transaction 69335:')
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE banking_transaction_id = 69335
    ORDER BY receipt_date
    """
)
rows = cur.fetchall()
for r in rows:
    print(f"  #{r[0]} | {r[1]} | {r[2]} | ${r[3]:.2f} | {r[4]}")

print('\nSearch receipts 2012-09-12..2012-09-20 with vendor ILIKE %fas%gas%:')
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, gross_amount
    FROM receipts
    WHERE receipt_date BETWEEN '2012-09-12' AND '2012-09-20'
      AND vendor_name ILIKE '%fas%gas%'
    ORDER BY receipt_date
    LIMIT 20
    """
)
rows = cur.fetchall()
for r in rows:
    print(f"  #{r[0]} | {r[1]} | {r[2]} | ${r[3]:.2f}")
if not rows:
    print('  (no rows)')

print('\nSearch receipts 2012-09-12..2012-09-20 with vendor ILIKE %run%empty%:')
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, gross_amount
    FROM receipts
    WHERE receipt_date BETWEEN '2012-09-12' AND '2012-09-20'
      AND vendor_name ILIKE '%run%empty%'
    ORDER BY receipt_date
    LIMIT 20
    """
)
rows = cur.fetchall()
for r in rows:
    print(f"  #{r[0]} | {r[1]} | {r[2]} | ${r[3]:.2f}")
if not rows:
    print('  (no rows)')

# Confirm if receipts were created from banking (check source_reference or created_from_banking if present)
print('\nSource reference for linked receipts:')
cur.execute(
    """
    SELECT receipt_id, source_reference
    FROM receipts
    WHERE banking_transaction_id = 69335
    ORDER BY receipt_id
    """
)
for r in cur.fetchall():
    print(f"  #{r[0]} | source={r[1]}")

conn.close()

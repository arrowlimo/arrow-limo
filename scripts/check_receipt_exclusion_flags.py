import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('Possible exclusion-related columns on receipts:')
cur.execute(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'receipts'
      AND (
        column_name ILIKE '%exclude%'
        OR column_name ILIKE '%delete%'
        OR column_name ILIKE '%void%'
        OR column_name ILIKE '%status%'
        OR column_name ILIKE '%arch%'
        OR column_name ILIKE '%hidden%'
        OR column_name ILIKE '%created_from_banking%'
        OR column_name ILIKE '%source_reference%'
      )
    ORDER BY column_name
    """
)
for r in cur.fetchall():
    print('  -', r[0])

print('\nReceipts for vendor RUN\'N ON EMPTY (2012-09-12..2012-09-20):')
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, gross_amount,
           banking_transaction_id, source_reference
    FROM receipts
    WHERE receipt_date BETWEEN '2012-09-12' AND '2012-09-20'
      AND vendor_name ILIKE '%run%empty%'
    ORDER BY receipt_date
    """
)
rows = cur.fetchall()
for r in rows:
    print(f"  #{r[0]} | {r[1]} | {r[2]} | ${r[3]:.2f} | bank_id={r[4]} | source={r[5]}")

conn.close()

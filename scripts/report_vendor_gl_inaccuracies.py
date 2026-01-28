import psycopg2

LIMIT = 50

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute(
    """
    SELECT 
        vendor_name,
        COUNT(*) AS receipt_count,
        SUM(gross_amount) AS total_amount,
        array_agg(DISTINCT gl_account_code) AS gl_codes,
        array_agg(DISTINCT gl_account_name) AS gl_names,
        array_agg(DISTINCT category) AS categories
    FROM receipts
    WHERE gl_account_code IS NULL
       OR gl_account_code = '6900'
       OR gl_account_code = '5850'
       OR LOWER(gl_account_name) LIKE '%unknown%'
       OR LOWER(category) LIKE '%unknown%'
       OR LOWER(category) LIKE '%uncategorized%'
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
    LIMIT 50
    """
)

rows = cur.fetchall()
print(f"Top {LIMIT} vendors with unknown/uncategorized GL flags:")
print(f"{'Vendor':<45} {'Count':>6} {'Total':>14}  GL Codes / Categories")
print('-' * 120)
for r in rows:
    vendor, count, total, gls, gl_names, cats = r
    total = total or 0
    gls = ','.join([g or 'NULL' for g in gls if g is not None])
    gl_names = ','.join([g or 'NULL' for g in gl_names if g is not None])
    cats = ','.join([c or 'NULL' for c in cats if c is not None])
    print(f"{vendor[:44]:<45} {count:>6} ${total:>13,.2f}  GL:{gls} | Cats:{cats}")

conn.close()

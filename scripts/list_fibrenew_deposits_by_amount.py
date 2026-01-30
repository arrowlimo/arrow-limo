import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
      AND gl_account_code = '4110'
    ORDER BY gross_amount DESC, receipt_date
""")

print(f"{'ID':<8} {'Date':<12} {'Amount':>12}")
print('-'*40)
for r in cur.fetchall():
    print(f"{r[0]:<8} {str(r[1]):<12} ${r[2]:>11,.2f}")

cur.close()
conn.close()

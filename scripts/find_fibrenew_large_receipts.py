import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gl_account_code, gross_amount, gl_account_name
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%fibrenew%'
      AND gross_amount BETWEEN 2400 AND 3200
    ORDER BY receipt_date
""")

print(f"{'ID':<8} {'Date':<12} {'GL':<6} {'Amount':>12} {'GL Name':<25}")
print('-'*70)
rows = cur.fetchall()
for r in rows:
    print(f"{r[0]:<8} {str(r[1]):<12} {str(r[3] or 'NULL'):<6} ${r[4]:>11,.2f} {str(r[5] or '')[:24]}")

cur.close()
conn.close()

import psycopg2
from decimal import Decimal

target = Decimal('1034.05')

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gl_account_code, gross_amount
    FROM receipts
    WHERE ABS(gross_amount - %s::numeric) < 0.01
    ORDER BY receipt_date
""", (target,))

print(f"Receipts with amount ~$ {target}:")
for r in cur.fetchall():
    print(f"{r[0]:<8} {str(r[1]):<12} {r[2][:30]:<30} GL {str(r[3] or 'NULL'):<5} ${r[4]:>11,.2f}")

cur.close()
conn.close()

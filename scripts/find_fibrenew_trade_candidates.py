import psycopg2
from decimal import Decimal, ROUND_HALF_UP

targets = [
    Decimal('2500.00'),
    Decimal('1034.05'),
]

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("Fibrenew GL 4110 receipts matching trade amounts (~$2,500 and ~$1,034.05):")
print(f"{'ID':<8} {'Date':<12} {'Amount':>12}")
print('-'*36)

found_ids = []
for amt in targets:
    cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount
            FROM receipts
            WHERE vendor_name ILIKE '%%fibrenew%%'
                AND gl_account_code = '4110'
                AND ABS(gross_amount - %s::numeric) < 0.01
            ORDER BY receipt_date
    """, (amt,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            found_ids.append(r[0])
            print(f"{r[0]:<8} {str(r[1]):<12} ${r[2]:>11,.2f}")
    else:
        print(f"(none found for ${amt})")

print(f"\nMatched receipt IDs: {found_ids}")

conn.close()

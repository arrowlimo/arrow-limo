#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check how many revenue receipts we're finding
cur.execute("""
    SELECT COUNT(*), SUM(revenue)
    FROM receipts
    WHERE revenue IS NOT NULL AND revenue > 0
      AND (
            vendor_name ILIKE 'customer payment%' OR
            vendor_name ILIKE 'square%' OR
            vendor_name ILIKE 'chq%' OR
            vendor_name ILIKE 'chk%' OR
            vendor_name ILIKE 'cheque%' OR
            canonical_vendor ILIKE 'square%' OR
            pay_method ILIKE 'square%' OR
            pay_method ILIKE 'email%' OR
            pay_method ILIKE 'e-transfer%' OR
            pay_method ILIKE 'etransfer%' OR
            payment_method ILIKE 'email%' OR
            payment_method ILIKE 'e-transfer%' OR
            payment_method ILIKE 'cheq%' OR
            payment_method ILIKE 'square%'
          )
""")
cnt, total = cur.fetchone()
total_display = f"${total:,.2f}" if total else "$0.00"
print(f"Total candidate receipts: {cnt:,}, Total revenue: {total_display}")

# Show examples
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, revenue, gross_amount, payment_method, pay_method, canonical_pay_method
    FROM receipts
    WHERE revenue IS NOT NULL AND revenue > 0
      AND (
            vendor_name ILIKE 'customer payment%' OR
            vendor_name ILIKE 'square%' OR
            vendor_name ILIKE 'chq%' OR
            vendor_name ILIKE 'chk%' OR
            vendor_name ILIKE 'cheque%' OR
            canonical_vendor ILIKE 'square%' OR
            pay_method ILIKE 'square%' OR
            pay_method ILIKE 'email%' OR
            pay_method ILIKE 'e-transfer%' OR
            pay_method ILIKE 'etransfer%' OR
            payment_method ILIKE 'email%' OR
            payment_method ILIKE 'e-transfer%' OR
            payment_method ILIKE 'cheq%' OR
            payment_method ILIKE 'square%'
          )
    ORDER BY receipt_date DESC
    LIMIT 20
""")
print("\nSample receipts:")
for row in cur.fetchall():
    rid, rdate, vendor, revenue, gross, pay_method, pay_method2, canonical_pay_method = row
    print(f"{rid:<8} {rdate} {vendor[:40]:<42} rev=${revenue or 0:>10.2f} gross=${gross or 0:>10.2f} pm={pay_method or ''}")

cur.close()
conn.close()

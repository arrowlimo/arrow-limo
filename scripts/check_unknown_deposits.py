import psycopg2

VENDORS = [
    'UNKNOWN PAYEE',
    'DEPOSIT',
    'DEPOSIT #X',
]

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Summary by vendor/GL for UNKNOWN PAYEE / DEPOSIT / DEPOSIT #X:")
cur.execute(
    """
    SELECT vendor_name, gl_account_code, gl_account_name, category,
           COUNT(*) AS cnt, SUM(gross_amount) AS total,
           MIN(receipt_date) AS first_date, MAX(receipt_date) AS last_date
    FROM receipts
    WHERE vendor_name = ANY(%s)
    GROUP BY vendor_name, gl_account_code, gl_account_name, category
    ORDER BY vendor_name, total DESC
    """,
    (VENDORS,),
)
rows = cur.fetchall()
print(f"{'Vendor':<15} {'GL':<8} {'GL Name':<30} {'Category':<25} {'Count':>6} {'Total':>14} {'First':<12} {'Last':<12}")
print('-'*130)
for r in rows:
    vendor, gl, gl_name, cat, cnt, total, first, last = r
    print(f"{vendor[:14]:<15} {str(gl or 'NULL'):<8} {str(gl_name or '')[:29]:<30} {str(cat or '')[:24]:<25} {cnt:>6} ${total:>13,.2f} {str(first):<12} {str(last):<12}")

print("\nTop 20 most recent receipts for these vendors:")
cur.execute(
    """
    SELECT vendor_name, receipt_id, receipt_date, gross_amount, gl_account_code, category, description
    FROM receipts
    WHERE vendor_name = ANY(%s)
    ORDER BY receipt_date DESC
    LIMIT 20
    """,
    (VENDORS,),
)
rows = cur.fetchall()
print(f"{'Vendor':<15} {'ID':<8} {'Date':<12} {'Amount':>12} {'GL':<8} {'Category':<25} Description")
print('-'*130)
for r in rows:
    vendor, rid, date, amt, gl, cat, desc = r
    print(f"{vendor[:14]:<15} {rid:<8} {str(date):<12} ${amt:>11,.2f} {str(gl or 'NULL'):<8} {str(cat or '')[:24]:<25} {str(desc or '')[:60]}")

conn.close()

"""
Report receipts where actual GST differs from calculated GST
Helps confirm override volumes and audit readiness.
"""
import os
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print('GST Override Audit')
print('='*60)

cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount,
           ROUND(gross_amount * 0.05 / 1.05, 2) AS calc_gst,
           (gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) AS delta
    FROM receipts
    WHERE gst_amount IS NOT NULL
    ORDER BY ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) DESC
    LIMIT 50;
    """
)
for row in cur.fetchall():
    receipt_id, receipt_date, vendor_name, gross, gst, calc_gst, delta = row
    if delta is not None and abs(delta) >= 0.01:
        print(f"#{receipt_id} {receipt_date} {vendor_name} gross={gross:.2f} gst={gst:.2f} calc={calc_gst:.2f} Δ={delta:.2f}")

cur.execute("SELECT COUNT(*) FROM receipts WHERE gst_amount IS NOT NULL")
count_with_gst = cur.fetchone()[0]

cur.execute(
    """
    SELECT COUNT(*) FROM receipts
    WHERE gst_amount IS NOT NULL
      AND gst_amount <> ROUND(gross_amount * 0.05 / 1.05, 2)
    """
)
count_overrides = cur.fetchone()[0]

print('\nTotals:')
print(f"  Receipts with GST recorded: {count_with_gst:,}")
print(f"  Receipts where actual GST differs from calculated: {count_overrides:,}")

cur.close()
conn.close()

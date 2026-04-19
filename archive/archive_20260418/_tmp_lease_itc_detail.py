import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
lease_regex = r'(LEASE|FORD\\s*CREDIT|TOYOTA\\s*CREDIT|GM\\s*FINANCIAL|MERCEDES|HONDA\\s*FINANCE|VEHICLE\\s*LEASE|AUTO\\s*LEASE|LOAN\\s*PAYMENT)'
cur.execute('''
WITH lease_receipts AS (
  SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_exempt,
         ROUND((COALESCE(gross_amount,0) * 0.05 / 1.05)::numeric, 2) AS expected_gst
  FROM receipts
  WHERE receipt_date >= DATE '2012-01-01' AND receipt_date < DATE '2015-01-01'
    AND (
      COALESCE(vendor_name,'') ~* %s OR COALESCE(canonical_vendor,'') ~* %s OR COALESCE(description,'') ~* %s OR COALESCE(category,'') ~* %s OR COALESCE(expense::text,'') ~* %s
    )
)
SELECT
  COUNT(*) AS cnt,
  COUNT(*) FILTER (WHERE COALESCE(gst_exempt,false)=false AND COALESCE(gst_amount,0)=0) AS zero_gst,
  COUNT(*) FILTER (WHERE COALESCE(gst_exempt,false)=false AND ABS(COALESCE(gst_amount,0)-expected_gst) > 0.05) AS outlier
FROM lease_receipts
''', (lease_regex,lease_regex,lease_regex,lease_regex,lease_regex))
print(cur.fetchone())
cur.execute('''
WITH lease_receipts AS (
  SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_exempt,
         ROUND((COALESCE(gross_amount,0) * 0.05 / 1.05)::numeric, 2) AS expected_gst
  FROM receipts
  WHERE receipt_date >= DATE '2012-01-01' AND receipt_date < DATE '2015-01-01'
    AND (
      COALESCE(vendor_name,'') ~* %s OR COALESCE(canonical_vendor,'') ~* %s OR COALESCE(description,'') ~* %s OR COALESCE(category,'') ~* %s OR COALESCE(expense::text,'') ~* %s
    )
)
SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, expected_gst
FROM lease_receipts
WHERE COALESCE(gst_exempt,false)=false AND ABS(COALESCE(gst_amount,0)-expected_gst) > 0.05
ORDER BY receipt_date, receipt_id
LIMIT 20
''', (lease_regex,lease_regex,lease_regex,lease_regex,lease_regex))
for r in cur.fetchall():
  print(r)
cur.close(); conn.close()

import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=%s
  AND COALESCE(gross_amount,0)>0
  AND (
        COALESCE(category,'') ILIKE '%%lease%%'
     OR COALESCE(description,'') ILIKE '%%lease%%'
     OR COALESCE(vendor_name,'') ILIKE '%%lease%%'
      )
  AND COALESCE(gst_amount,0)=0
""", (2012,))
print(dict(cur.fetchone()))
cur.close(); conn.close()

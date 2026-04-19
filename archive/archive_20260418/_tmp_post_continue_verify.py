import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""SELECT COUNT(*) cnt, COALESCE(SUM(amount),0) amt FROM charter_payments WHERE charter_id IS NULL AND EXTRACT(YEAR FROM payment_date) IN (2025,2026)""")
print('remaining_unlinked_2025_2026:', dict(cur.fetchone()))
cur.execute("""
SELECT COUNT(*) cnt, COALESCE(SUM(debit_amount),0) amt
FROM banking_transactions
WHERE COALESCE(debit_amount,0)>0 AND receipt_id IS NULL
""")
print('remaining_all_unlinked_debits:', dict(cur.fetchone()))
cur.execute("""
SELECT COUNT(*) cnt, COALESCE(SUM(debit_amount),0) amt
FROM banking_transactions
WHERE COALESCE(debit_amount,0)>0
  AND receipt_id IS NULL
  AND (
    COALESCE(vendor_extracted,'') ILIKE '%HEFFNER%'
    OR COALESCE(vendor_extracted,'') ILIKE '%TELUS%'
    OR COALESCE(vendor_extracted,'') ILIKE '%ASI%'
    OR COALESCE(vendor_extracted,'') ILIKE '%ALL SERVICE INSURANCE%'
    OR COALESCE(vendor_extracted,'') ILIKE '%ROGERS%'
    OR COALESCE(vendor_extracted,'') ILIKE '%ERLES%'
    OR COALESCE(vendor_extracted,'') ILIKE '%KAL TIRE%'
    OR COALESCE(vendor_extracted,'') ILIKE '%FAS GAS%'
    OR COALESCE(vendor_extracted,'') ILIKE '%PETRO%'
    OR COALESCE(vendor_extracted,'') ILIKE '%SHELL%'
  )
""")
print('remaining_priority_vendor_unlinked_debits:', dict(cur.fetchone()))
cur.close(); conn.close()

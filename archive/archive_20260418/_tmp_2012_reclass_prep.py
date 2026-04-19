import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)

print('=== COA TARGET CODES ===')
cur.execute("""
SELECT account_code, account_name, account_type
FROM chart_of_accounts
WHERE account_code IN ('5300','5400','5720','6300','5110','5100')
ORDER BY account_code
""")
print(cur.fetchall())

print('\n=== TARGET COUNTS IN 409 REVIEW SET ===')
cur.execute("""
SELECT 'HEFFNER' grp, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND (COALESCE(vendor_name,'') ILIKE '%HEFFNER%' OR COALESCE(description,'') ILIKE '%HEFFNER%')
UNION ALL
SELECT 'IFS_PREMIUM_FINANCE' grp, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND (COALESCE(vendor_name,'') ILIKE '%IFS%' OR COALESCE(description,'') ILIKE '%IFS PREMIUM%')
UNION ALL
SELECT 'REGISTRIES' grp, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND (COALESCE(vendor_name,'') ILIKE '%REGISTR%' OR COALESCE(description,'') ILIKE '%REGISTR%')
UNION ALL
SELECT 'VCARD_MCARD' grp, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND (COALESCE(vendor_name,'') ILIKE '%VCARD PAYMENT%' OR COALESCE(vendor_name,'') ILIKE '%MCARD PAYMENT%' OR COALESCE(description,'') ILIKE '%VCARD PAYMENT%' OR COALESCE(description,'') ILIKE '%MCARD PAYMENT%')
UNION ALL
SELECT 'FUEL_VENDOR_LIKE' grp, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=2012
  AND receipt_source='auto_2012_unlinked_debit_review_backfill'
  AND (
    COALESCE(vendor_name,'') ILIKE '%SHELL%'
    OR COALESCE(vendor_name,'') ILIKE '%PETRO%'
    OR COALESCE(vendor_name,'') ILIKE '%HUSKY%'
    OR COALESCE(vendor_name,'') ILIKE '%CO-OP GAS%'
    OR COALESCE(vendor_name,'') ILIKE '%FAS GAS%'
    OR COALESCE(vendor_name,'') ILIKE '%RUNNING ON EMPTY%'
    OR COALESCE(vendor_name,'') ILIKE '%RUN''N ON EMPTY%'
  )
""")
for r in cur.fetchall():
    print(dict(r))

cur.close(); conn.close()

from datetime import date
import psycopg2
from modern_backend.app.tax.t2_data_extraction import T2DataExtractor

year=2025
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor()
cur.execute("""
SELECT COALESCE(gl_account_code,'UNASSIGNED') AS gl, COUNT(*)
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date)=%s
GROUP BY COALESCE(gl_account_code,'UNASSIGNED')
""", (year,))
receipt_gl={row[0] for row in cur.fetchall()}
cur.close(); conn.close()

ext=T2DataExtractor({'dbname':'almsdata','user':'postgres','password':'ArrowLimousine','host':'localhost'})
analysis=ext.extract_t2_deductibility_analysis(year)
report_gl={r['gl_code'] for r in analysis['by_gl_code']}

print('receipt distinct gl:', len(receipt_gl))
print('deductibility gl rows:', len(report_gl))
print('missing in deductibility:', sorted(receipt_gl-report_gl)[:100])
print('extra in deductibility:', sorted(report_gl-receipt_gl)[:100])

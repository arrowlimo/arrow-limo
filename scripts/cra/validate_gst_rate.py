#!/usr/bin/env python
import psycopg2

c = psycopg2.connect('dbname=almsdata user=postgres password=***REMOVED***')
r = c.cursor()

r.execute("""
    SELECT SUM(COALESCE(credit,0)-COALESCE(debit,0)) 
    FROM general_ledger 
    WHERE account IN ('4000 Limousine Service Income','4300 Gratuity Income','4800 Other Income') 
    AND date BETWEEN '2025-07-01' AND '2025-09-30'
""")
rev = r.fetchone()[0]

r.execute("""
    SELECT SUM(COALESCE(credit,0)-COALESCE(debit,0)) 
    FROM general_ledger 
    WHERE account IN ('2200 GST/HST Payable','GST/HST Payable') 
    AND date BETWEEN '2025-07-01' AND '2025-09-30'
""")
gst = r.fetchone()[0]

print(f'2025 Q3 GST Validation:')
print(f'  Revenue:        ${rev:,.2f}')
print(f'  GST Collected:  ${gst:,.2f}')
print(f'  Actual Rate:    {(gst/rev*100):.2f}%')
print(f'  Expected @5%:   ${rev*0.05:,.2f}')
print(f'  Difference:     ${rev*0.05 - gst:,.2f}')

c.close()

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT column_name FROM information_schema.columns
WHERE table_schema='public' AND table_name='receipts'
ORDER BY ordinal_position
""")
rcols = [r['column_name'] for r in cur.fetchall()]
print('receipts has amount column:', 'amount' in rcols)
print('receipts has gl_code column:', 'gl_code' in rcols)
print('receipts has gl_account_code column:', 'gl_account_code' in rcols)
print('receipts has exclude_from_reports column:', 'exclude_from_reports' in rcols)
print('receipts has is_personal_purchase column:', 'is_personal_purchase' in rcols)
print('receipts has owner_personal_amount column:', 'owner_personal_amount' in rcols)
print('receipts has business_personal column:', 'business_personal' in rcols)

print('\n=== NON-DEDUCTIBLE GL AMOUNTS IN RECEIPTS ===')
cur.execute("""
SELECT gl_account_code, COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt
FROM receipts
WHERE gl_account_code IN ('2550','2560','2910','3020','5880','6100')
GROUP BY gl_account_code
ORDER BY gl_account_code
""")
print(cur.fetchall())

print('\n=== PERSONAL/EXCLUDED RECEIPT EXPOSURE ===')
if 'exclude_from_reports' in rcols or 'is_personal_purchase' in rcols or 'owner_personal_amount' in rcols or 'business_personal' in rcols:
    ex = "COALESCE(SUM(CASE WHEN "
    parts = []
    if 'exclude_from_reports' in rcols:
        parts.append('COALESCE(exclude_from_reports,false)=true')
    if 'is_personal_purchase' in rcols:
        parts.append('COALESCE(is_personal_purchase,false)=true')
    if 'owner_personal_amount' in rcols:
        parts.append('COALESCE(owner_personal_amount,0)>0')
    if 'business_personal' in rcols:
        parts.append("LOWER(COALESCE(business_personal,'')) LIKE '%personal%'")
    cond = ' OR '.join(parts) if parts else 'false'
    cur.execute(f"""
    SELECT COUNT(*) cnt, COALESCE(SUM(gross_amount),0) amt,
           COALESCE(SUM(CASE WHEN {cond} THEN gross_amount ELSE 0 END),0) flagged_amt
    FROM receipts
    """)
    print(dict(cur.fetchone()))
else:
    print('No personal/exclude flag columns found in receipts')

print('\n=== CHARTER REVENUE FIELD CONSISTENCY ===')
cur.execute("""
SELECT
  COALESCE(SUM(total_amount_due),0) total_amount_due_sum,
  COALESCE(SUM(grand_total),0) grand_total_sum,
  COALESCE(SUM(balance),0) balance_sum,
  COALESCE(SUM(payment_totals),0) payment_totals_sum
FROM charters
WHERE status NOT IN ('cancelled','no-show')
""")
print(dict(cur.fetchone()))

cur.close()
conn.close()

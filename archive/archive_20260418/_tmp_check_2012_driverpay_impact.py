import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    """
    SELECT COALESCE(SUM(gross_amount),0) amt
    FROM receipts
    WHERE receipt_date >= '2012-01-01' AND receipt_date < '2013-01-01'
      AND COALESCE(is_voided,false)=false
      AND COALESCE(is_nsf,false)=false
      AND COALESCE(exclude_from_reports,false)=false
      AND COALESCE(revenue,0)=0
    """
)
base = float(cur.fetchone()['amt'])

cur.execute(
    """
    SELECT COUNT(*) c, COALESCE(SUM(gross_amount),0) amt
    FROM receipts
    WHERE receipt_date >= '2012-01-01' AND receipt_date < '2013-01-01'
      AND (
        COALESCE(is_driver_reimbursement, false) = true
        OR COALESCE(reimbursed_via, '') <> ''
        OR COALESCE(category, '') ILIKE 'Driver Pay'
        OR COALESCE(category, '') ILIKE 'Driver Payment'
        OR COALESCE(classification, '') ILIKE 'Driver Pay'
        OR COALESCE(classification, '') ILIKE 'Driver Payment'
        OR COALESCE(description, '') ILIKE '%%Driver Pay%%'
        OR COALESCE(description, '') ILIKE '%%Driver Payment%%'
        OR COALESCE(description, '') ILIKE '%%driver reimbursement%%'
        OR COALESCE(description, '') ILIKE '%%payroll reimbursement%%'
      )
    """
)
r = cur.fetchone()
driver_cnt = int(r['c'])
driver_amt = float(r['amt'])

print("2012_book_expense_base", base)
print("2012_driver_pay_receipts", driver_cnt)
print("2012_driver_pay_amount", driver_amt)
print("2012_adjusted_expense_excluding_driver_pay", base - driver_amt)

conn.close()

"""
List 2012 charters where charter.paid_amount != SUM(payments.amount by reserve_number in 2012)
Outputs top 50 by absolute difference.
"""
import os
import psycopg2
from datetime import date

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
}

YEAR=2012

SQL='''
WITH pay AS (
  SELECT reserve_number, COALESCE(SUM(amount),0) AS paid
  FROM payments
  WHERE payment_date >= %s AND payment_date < %s
    AND reserve_number IS NOT NULL
  GROUP BY reserve_number
)
SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount,
       COALESCE(pay.paid,0) AS paid_2012,
       (c.paid_amount - COALESCE(pay.paid,0)) AS diff
FROM charters c
LEFT JOIN pay ON pay.reserve_number = c.reserve_number
WHERE c.charter_date >= %s AND c.charter_date < %s
  AND ABS(c.paid_amount - COALESCE(pay.paid,0)) >= 0.01
ORDER BY ABS(c.paid_amount - COALESCE(pay.paid,0)) DESC
LIMIT 50
'''

def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    s, e = date(YEAR,1,1), date(YEAR+1,1,1)
    cur.execute(SQL, (s,e,s,e))
    rows = cur.fetchall()
    print(f"Top 50 2012 mismatches (charter paid vs 2012 payments): {len(rows)}")
    print(f"{'Reserve':<8} {'Date':<10} {'Due':>10} {'Paid(c)':>10} {'Paid(2012)':>12} {'Diff':>10}")
    print('-'*65)
    for r in rows:
        print(f"{r[0]:<8} {r[1]} {r[2]:>10.2f} {r[3]:>10.2f} {r[4]:>12.2f} {r[5]:>10.2f}")
    cur.close(); conn.close()

if __name__=='__main__':
    main()

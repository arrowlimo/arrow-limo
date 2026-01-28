"""
Normalize payment methods and report revenue classification:
- Exclude cancelled charters from revenue
- Separate bank transfers into e_transfer vs ach (where possible)
- Group Visa/MasterCard/Amex as credit_card (via square_* fields or method)
- Classify cash, check (check_number), refunds, deposits (timing)
- Flag unknowns for cleanup

This script creates (or replaces) a view `payments_tender_normalized` and prints a summary.
"""
import psycopg2
from decimal import Decimal

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')


def fmt(x):
    if x is None:
        return '$0.00'
    if isinstance(x, Decimal):
        x = float(x)
    return f"${x:,.2f}"

SQL_CREATE_VIEW = """
CREATE OR REPLACE VIEW payments_tender_normalized AS
WITH base AS (
  SELECT 
    p.payment_id,
    p.charter_id,
    p.amount,
    p.payment_date,
    LOWER(TRIM(p.payment_method)) AS method_raw,
    p.check_number,
    p.square_card_brand,
    p.square_last4,
    p.payment_key,
    p.notes,
    c.status AS charter_status
  FROM payments p
  LEFT JOIN charters c USING (charter_id)
)
, nature AS (
  SELECT 
    *,
    CASE 
      WHEN amount < 0 THEN 'refund'
      WHEN method_raw = 'refund' THEN 'refund'
      WHEN payment_key LIKE 'LMSDEP:%' OR method_raw = 'deposit' OR notes ILIKE '%deposit%' THEN 'deposit'
      ELSE 'payment'
    END AS payment_nature
  FROM base
)
SELECT 
  n.payment_id,
  n.charter_id,
  n.amount,
  n.payment_date,
  n.method_raw,
  n.check_number,
  n.square_card_brand,
  n.square_last4,
  n.payment_key,
  n.notes,
  n.charter_status,
  n.payment_nature,
  CASE 
    WHEN n.method_raw = 'cash' THEN 'cash'
    WHEN n.method_raw IN ('check','cheque','chk') OR n.check_number IS NOT NULL THEN 'check'
    WHEN n.method_raw IN ('credit','credit_card','card') OR n.square_card_brand IS NOT NULL THEN 'credit_card'
    WHEN n.method_raw IN ('bank_transfer','bank','transfer','e-transfer','etransfer','interac','ach') THEN 
      CASE WHEN n.payment_key LIKE 'BTX:%' OR n.notes ILIKE '%interac%' OR n.notes ILIKE '%e-transfer%' OR n.notes ILIKE '%etransfer%'
           THEN 'e_transfer' ELSE 'ach' END
    WHEN n.method_raw IS NULL OR n.method_raw = '' THEN 
      CASE WHEN n.square_card_brand IS NOT NULL THEN 'credit_card'
           WHEN n.check_number IS NOT NULL THEN 'check'
           ELSE 'unknown' END
    ELSE n.method_raw
  END AS tender_type,
  CASE WHEN COALESCE(n.charter_status,'') IN ('cancelled','Cancelled') THEN TRUE ELSE FALSE END AS is_cancelled_charter,
  CASE WHEN n.amount > 0 AND n.payment_nature = 'payment' AND NOT (COALESCE(n.charter_status,'') IN ('cancelled','Cancelled')) THEN TRUE ELSE FALSE END AS include_in_revenue
FROM nature n;
"""

SQL_SUMMARY = """
WITH s AS (
  SELECT tender_type,
         payment_nature,
         include_in_revenue,
         COUNT(*) AS cnt,
         COALESCE(SUM(amount),0) AS total
  FROM payments_tender_normalized
  GROUP BY 1,2,3
)
SELECT tender_type,
       payment_nature,
       include_in_revenue,
       cnt,
       total
FROM s
ORDER BY tender_type, payment_nature, include_in_revenue DESC;
"""

SQL_CANCELLED_IMPACT = """
SELECT 
  COUNT(*) AS payments_linked_to_cancelled,
  COALESCE(SUM(amount),0) AS amount
FROM payments_tender_normalized
WHERE is_cancelled_charter = TRUE;
"""

SQL_UNKNOWN = """
SELECT COUNT(*) AS unknown_cnt, COALESCE(SUM(amount),0) AS unknown_total
FROM payments_tender_normalized
WHERE tender_type = 'unknown';
"""

SQL_METHOD_DISTINCT = """
SELECT DISTINCT COALESCE(NULLIF(LOWER(TRIM(payment_method)),''), '(null)') AS method_raw
FROM payments
WHERE charter_id IS NOT NULL
ORDER BY 1 NULLS FIRST;
"""

SQL_FAILED_TO_PAY = """
SELECT COUNT(*) AS charters_without_payments,
       COALESCE(SUM(c.balance),0) AS outstanding_balance
FROM charters c
LEFT JOIN payments p ON p.charter_id = c.charter_id
WHERE COALESCE(c.status,'') NOT IN ('cancelled','Cancelled')
  AND p.charter_id IS NULL
  AND COALESCE(c.balance,0) > 0;
"""

def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    print('='*80)
    print('Creating payments_tender_normalized view (idempotent)')
    print('='*80)
    cur.execute(SQL_CREATE_VIEW)
    conn.commit()

    print('\nSummary by tender_type × payment_nature × include_in_revenue:')
    cur.execute(SQL_SUMMARY)
    rows = cur.fetchall()
    print(f"{'tender_type':<14} {'nature':<10} {'in_rev':<7} {'count':>10} {'amount':>18}")
    print('-'*70)
    for ttype, nature, in_rev, cnt, total in rows:
        print(f"{ttype:<14} {nature:<10} {str(in_rev):<7} {cnt:>10,} {fmt(total):>18}")

    print('\nImpact of cancelled charters (should be excluded from revenue):')
    cur.execute(SQL_CANCELLED_IMPACT)
    c_cnt, c_amt = cur.fetchone()
    print(f"Payments linked to cancelled charters: {c_cnt:,} | {fmt(c_amt)}")

    print('\nUnknown tender_type to resolve:')
    cur.execute(SQL_UNKNOWN)
    u_cnt, u_amt = cur.fetchone()
    print(f"Unknown tender_type: {u_cnt:,} | {fmt(u_amt)}")

    print('\nPotential failed-to-pay (no payments, non-cancelled charters):')
    cur.execute(SQL_FAILED_TO_PAY)
    f_cnt, f_amt = cur.fetchone()
    print(f"Charters without payments: {f_cnt:,} | Outstanding: {fmt(f_amt)}")

    print('\nDistinct raw payment_method values (charter-linked):')
    cur.execute(SQL_METHOD_DISTINCT)
    distinct = [r[0] for r in cur.fetchall()]
    for v in distinct:
        print(f"  - {v}")

    cur.close()
    conn.close()
    print('\nDone.')

if __name__ == '__main__':
    main()

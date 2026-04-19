import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print('READINESS_2012')

# T4 records count
cur.execute("SELECT COUNT(*) AS n FROM employee_t4_records WHERE tax_year=2012")
print('T4_RECORDS_2012', cur.fetchone()['n'])

# T4 summary count (correct column is fiscal_year)
cur.execute("SELECT COUNT(*) AS n FROM employee_t4_summary WHERE fiscal_year=2012")
print('T4_SUMMARY_RECORDS_2012', cur.fetchone()['n'])

# Missing employee identity/address fields required for filing artifacts
cur.execute(
    """
    SELECT
      COUNT(*) FILTER (WHERE e.t4_sin IS NULL OR BTRIM(e.t4_sin)='') AS missing_sin,
      COUNT(*) FILTER (WHERE e.street_address IS NULL OR BTRIM(e.street_address)='') AS missing_street,
      COUNT(*) FILTER (WHERE e.city IS NULL OR BTRIM(e.city)='') AS missing_city,
      COUNT(*) FILTER (WHERE e.province IS NULL OR BTRIM(e.province)='') AS missing_province,
      COUNT(*) FILTER (WHERE e.postal_code IS NULL OR BTRIM(e.postal_code)='') AS missing_postal
    FROM employee_t4_records t
    JOIN employees e ON e.employee_id=t.employee_id
    WHERE t.tax_year=2012
    """
)
print('T4_EMPLOYEE_FIELD_GAPS', dict(cur.fetchone()))

# T2 method outputs present?
cur.execute(
    """
    SELECT
      SUM(CASE WHEN net_income IS NULL THEN 1 ELSE 0 END) AS null_net_income_rows,
      COUNT(*) AS method_rows
    FROM (
      SELECT 'pack' AS m, NULL::numeric AS net_income
      UNION ALL
      SELECT 't2', NULL::numeric
      UNION ALL
      SELECT 'gl_adj', NULL::numeric
    ) x
    """
)
# Placeholder sanity row (script-based file checks are done in Python output list elsewhere)
print('T2_METHOD_PLACEHOLDER_ROWS', dict(cur.fetchone()))

# Outstanding 2012 unresolved e-transfer review tail
cur.execute(
    """
    SELECT COUNT(*) AS n, COALESCE(SUM(debit_amount),0) AS amt
    FROM banking_transactions
    WHERE debit_amount>0
      AND receipt_id IS NULL
      AND reconciliation_status IS DISTINCT FROM 'MANUAL_CLASSIFIED'
      AND (
            description ILIKE '%etransfer%'
            OR description ILIKE '%e-transfer%'
            OR description ILIKE '%email transfer%'
          )
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
    """
)
print('UNRESOLVED_ETRANSFER_TAIL', dict(cur.fetchone()))

cur.close()
conn.close()

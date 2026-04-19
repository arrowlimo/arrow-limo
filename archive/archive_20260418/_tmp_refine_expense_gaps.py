import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

base = """
COALESCE(is_voided, false) = false
AND COALESCE(is_nsf, false) = false
AND COALESCE(exclude_from_reports, false) = false
AND COALESCE(revenue, 0) = 0
"""

queries = {
    "base_count_amt": f"SELECT COUNT(*) c, COALESCE(SUM(gross_amount),0) a FROM receipts WHERE {base}",
    "missing_category": f"SELECT COUNT(*) c, COALESCE(SUM(gross_amount),0) a FROM receipts WHERE {base} AND (category IS NULL OR TRIM(category)='')",
    "missing_gl_both": f"SELECT COUNT(*) c, COALESCE(SUM(gross_amount),0) a FROM receipts WHERE {base} AND ((gl_code IS NULL OR TRIM(gl_code)='') AND (gl_account_code IS NULL OR TRIM(gl_account_code)=''))",
    "missing_expense_account": f"SELECT COUNT(*) c, COALESCE(SUM(gross_amount),0) a FROM receipts WHERE {base} AND (expense_account IS NULL OR TRIM(expense_account)='')",
}

for name, q in queries.items():
    cur.execute(q)
    r = cur.fetchone()
    print(name, int(r['c']), float(r['a']))

conn.close()

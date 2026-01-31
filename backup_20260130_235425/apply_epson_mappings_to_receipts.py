import sys
import pathlib
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import get_db_connection  # type: ignore

"""
Apply Epson mappings to receipts:
- For each receipt with Epson fields (classification, pay_account, pay_method),
  populate mapping columns and posting targets.
Assumptions:
- receipts table has columns: id, classification, pay_account, pay_method,
  mapped_expense_account_id, mapped_bank_account_id, canonical_pay_method, mapping_status.
If these columns are missing, this script will create them.
"""

DDL = """
CREATE TABLE IF NOT EXISTS receipts (
  id SERIAL PRIMARY KEY
);
ALTER TABLE IF EXISTS receipts
  ADD COLUMN IF NOT EXISTS classification TEXT NULL,
  ADD COLUMN IF NOT EXISTS pay_account TEXT NULL,
  ADD COLUMN IF NOT EXISTS pay_method TEXT NULL,
  ADD COLUMN IF NOT EXISTS mapped_expense_account_id INTEGER NULL REFERENCES chart_of_accounts(account_id),
  ADD COLUMN IF NOT EXISTS mapped_bank_account_id INTEGER NULL REFERENCES chart_of_accounts(account_id),
  ADD COLUMN IF NOT EXISTS canonical_pay_method TEXT NULL,
  ADD COLUMN IF NOT EXISTS mapping_status VARCHAR(20) NULL,
  ADD COLUMN IF NOT EXISTS mapping_notes TEXT NULL;
"""

def build_update_sql(cur) -> str:
    # Detect available columns on receipts
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='receipts'
    """)
    cols = {r[0] for r in cur.fetchall()}
    has_category = 'category' in cols
    has_pay_account = 'pay_account' in cols
    has_pay_method = 'pay_method' in cols

    class_expr = "COALESCE(TRIM(r.classification), TRIM(r.category), '')" if has_category else "COALESCE(TRIM(r.classification),'')"
    pay_account_expr = "COALESCE(TRIM(r.pay_account),'')" if has_pay_account else "''"
    pay_method_expr = "COALESCE(TRIM(r.pay_method),'')" if has_pay_method else "''"

    sql = f"""
    WITH s AS (
      SELECT r.id,
             ecm.mapped_account_id AS expense_acct_id,
             epm.mapped_account_id AS bank_acct_id,
             em.canonical_method AS canonical_method,
             CASE
               WHEN (ecm.mapped_account_id IS NOT NULL AND epm.mapped_account_id IS NOT NULL AND (em.canonical_method IS NOT NULL OR {pay_method_expr} = '')) THEN 'approved'
               WHEN (ecm.mapped_account_id IS NOT NULL OR epm.mapped_account_id IS NOT NULL OR em.canonical_method IS NOT NULL) THEN 'partial'
               ELSE 'unmapped'
             END AS status
      FROM receipts r
      LEFT JOIN epson_classifications_map ecm ON {class_expr} = ecm.epson_classification
      LEFT JOIN epson_pay_accounts_map epm ON {pay_account_expr} = epm.epson_pay_account
      LEFT JOIN epson_pay_methods_map em ON {pay_method_expr} = em.epson_pay_method
      WHERE COALESCE(r.mapping_status,'') IN ('', 'unmapped', 'partial') OR r.mapping_status IS NULL
    )
    UPDATE receipts r
    SET mapped_expense_account_id = s.expense_acct_id,
        mapped_bank_account_id = s.bank_acct_id,
        canonical_pay_method = s.canonical_method,
        mapping_status = s.status
    FROM s
    WHERE r.id = s.id;
    """
    return sql

COUNT_SQL = """
SELECT 
  SUM(CASE WHEN mapping_status = 'approved' THEN 1 ELSE 0 END) AS approved,
  SUM(CASE WHEN mapping_status = 'partial' THEN 1 ELSE 0 END) AS partial,
  SUM(CASE WHEN COALESCE(mapping_status,'') = '' OR mapping_status = 'unmapped' THEN 1 ELSE 0 END) AS unmapped,
  COUNT(*) AS total
FROM receipts;
"""

def main():
  conn = get_db_connection()
  conn.autocommit = False
  try:
    cur = conn.cursor()
    cur.execute(DDL)
    # Backfill classification from category when missing (only if category column exists)
    cur.execute("""
      DO $$
      BEGIN
        IF EXISTS (
          SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='receipts' AND column_name='category'
        ) THEN
          EXECUTE 'UPDATE receipts SET classification = COALESCE(classification, category) WHERE classification IS NULL AND category IS NOT NULL';
        END IF;
      END
      $$;
    """)
    update_sql = build_update_sql(cur)
    cur.execute(update_sql)
    conn.commit()
    cur.execute(COUNT_SQL)
    row = cur.fetchone()
    print({
      'approved': int(row[0] or 0),
      'partial': int(row[1] or 0),
      'unmapped': int(row[2] or 0),
      'total': int(row[3] or 0),
    })
  except Exception as e:
    conn.rollback()
    print(f"[ERROR] {e}")
    raise
  finally:
    conn.close()

if __name__ == '__main__':
    main()

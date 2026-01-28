import os
import sys
import csv
from pathlib import Path
import psycopg2
from typing import List, Tuple

# Ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import get_db_connection

OUT_DIR = Path(__file__).resolve().parents[1] / 'reports' / 'reference_lists'
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES: List[Tuple[str, str]] = [
    (
        'chart_of_accounts.csv',
        """
        SELECT account_code, account_name, account_type, account_subtype, normal_balance, COALESCE(is_active,true) AS is_active
        FROM chart_of_accounts
        ORDER BY account_type, account_code
        """
    ),
    (
        'bank_accounts.csv',
        """
        SELECT account_code, account_name, account_type, account_subtype
        FROM chart_of_accounts
        WHERE LOWER(account_type) IN ('asset')
          AND (LOWER(account_subtype) LIKE '%bank%' OR LOWER(account_name) LIKE '%bank%' OR LOWER(account_name) LIKE '%cash%')
        ORDER BY account_name
        """
    ),
    (
        'cash_flow_categories.csv',
        """
        SELECT category_id, category_name, category_type
        FROM cash_flow_categories
        ORDER BY category_name
        """
    ),
    (
        'square_payment_categories.csv',
        """
        SELECT DISTINCT category
        FROM square_payment_categories
        ORDER BY 1
        """
    ),
    (
        'payment_methods_distinct.csv',
        """
        WITH methods AS (
            SELECT LOWER(TRIM(payment_method)) AS m FROM payments WHERE payment_method IS NOT NULL
            UNION
            SELECT LOWER(TRIM(payment_method)) FROM payables WHERE payment_method IS NOT NULL
            UNION
            SELECT LOWER(TRIM(payment_method)) FROM personal_expenses WHERE payment_method IS NOT NULL
            UNION
            SELECT LOWER(TRIM(payment_method)) FROM trip_financial_transactions WHERE payment_method IS NOT NULL
            UNION
            SELECT LOWER(TRIM(payment_method)) FROM employee_payments WHERE payment_method IS NOT NULL
            UNION
            SELECT LOWER(TRIM(payment_type)) FROM deposit_records WHERE payment_type IS NOT NULL
        )
        SELECT DISTINCT m AS payment_method
        FROM methods
        WHERE m <> ''
        ORDER BY 1
        """
    ),
    (
        'receipts_payment_methods.csv',
        """
        SELECT DISTINCT LOWER(TRIM(payment_method)) AS payment_method
        FROM receipts
        WHERE payment_method IS NOT NULL AND TRIM(payment_method) <> ''
        ORDER BY 1
        """
    ),
    (
        'all_categories_gl_like.csv',
        """
        WITH cats AS (
            SELECT LOWER(TRIM(category)) AS c FROM accounting_records WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM bank_transactions_staging WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM beverages WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM business_losses WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM maintenance_activity_types WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM maintenance_service_types WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM major_events WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM payables WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM personal_expenses WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM personal_expenses_summary WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM vehicle_document_alerts WHERE category IS NOT NULL
            UNION SELECT LOWER(TRIM(category)) FROM vehicle_document_types WHERE category IS NOT NULL
        )
        SELECT DISTINCT c AS category
        FROM cats WHERE c <> ''
        ORDER BY 1
        """
    )
]


def run_query_to_csv(cur, filename: str, sql: str):
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out_path = OUT_DIR / filename
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f'Wrote {out_path}')


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    for fname, sql in QUERIES:
        try:
            run_query_to_csv(cur, fname, sql)
        except Exception as e:
            print(f'Query failed for {fname}: {e}')

    # Convenience: list of candidate account tables
    with open(OUT_DIR / 'README.txt', 'w', encoding='utf-8') as f:
        f.write('Reference lists extracted for mapping Epson -> Accounting System\n')
        f.write('- chart_of_accounts.csv\n- bank_accounts.csv\n- cash_flow_categories.csv\n- square_payment_categories.csv\n')
        f.write('- payment_methods_distinct.csv\n- receipts_payment_methods.csv\n- all_categories_gl_like.csv\n')


if __name__ == '__main__':
    main()

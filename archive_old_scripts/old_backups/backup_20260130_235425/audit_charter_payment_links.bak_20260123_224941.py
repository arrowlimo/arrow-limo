import os
import csv
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

"""
Audit existing payment↔charter links and related hints.
Outputs CSVs into l:/limo/reports/ for review before implementing new auto-linking.

Generated files:
- charter_payment_reconciliation_summary.csv
- payments_linked_to_charters.csv
- charters_with_multiple_payments.csv
- payments_multi_charter_notes.csv
- charter_payment_references_export.csv (if table exists)
"""

OUTPUT_DIR = r"l:/limo/reports"

QUERIES = {
    "payments_linked_to_charters": {
        "sql": (
            "SELECT p.payment_id, p.payment_key, p.payment_date, p.amount, p.payment_method, "
            "p.square_payment_id, p.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, p.notes "
            "FROM payments p LEFT JOIN charters c ON p.charter_id = c.charter_id "
            "WHERE p.charter_id IS NOT NULL ORDER BY p.payment_date DESC NULLS LAST"
        ),
        "filename": "payments_linked_to_charters.csv",
    },
    "charters_with_multiple_payments": {
        "sql": (
            "SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, COUNT(p.payment_id) AS num_payments, "
            "SUM(p.amount) AS sum_payments_amount FROM charters c LEFT JOIN payments p ON p.charter_id = c.charter_id "
            "GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due HAVING COUNT(p.payment_id) > 1 "
            "ORDER BY num_payments DESC, sum_payments_amount DESC NULLS LAST"
        ),
        "filename": "charters_with_multiple_payments.csv",
    },
    "payments_multi_charter_notes": {
        "sql": (
            "SELECT p.payment_id, p.payment_key, p.payment_date, p.amount, p.notes FROM payments p "
            "WHERE (p.notes ~ '#\\d{3,6}.*#\\d{3,6}') OR (p.notes ~ '\\b0\\d{5}.*0\\d{5}\\b') "
            "ORDER BY p.payment_date DESC NULLS LAST"
        ),
        "filename": "payments_multi_charter_notes.csv",
    },
}

OPTIONAL_OBJECTS = {
    "charter_payment_reconciliation_summary": {
        "exists_sql": "SELECT to_regclass('public.charter_payment_reconciliation_summary')",
        "sql": "SELECT * FROM charter_payment_reconciliation_summary ORDER BY charter_date DESC NULLS LAST",
        "filename": "charter_payment_reconciliation_summary.csv",
    },
    "charter_payment_references_export": {
        "exists_sql": "SELECT to_regclass('public.charter_payment_references')",
        "sql": "SELECT * FROM charter_payment_references ORDER BY updated_at DESC NULLS LAST",
        "filename": "charter_payment_references_export.csv",
    }
}


def write_csv(cur, sql, path):
    cur.execute(sql)
    rows = cur.fetchall()
    colnames = [d[0] for d in cur.description]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(colnames)
        writer.writerows(rows)
    return len(rows)


def main():
    load_dotenv('l:/limo/.env')
    load_dotenv()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )
    # Avoid transaction aborts from a single failing SELECT; all queries are read-only
    conn.autocommit = True
    cur = conn.cursor()

    results = {}

    # Required queries
    for key, meta in QUERIES.items():
        path = os.path.join(OUTPUT_DIR, meta['filename'])
        try:
            count = write_csv(cur, meta['sql'], path)
            results[key] = {"path": path, "rows": count}
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            results[key] = {"path": path, "error": str(e)}

    # Optional tables/views
    for key, meta in OPTIONAL_OBJECTS.items():
        try:
            cur.execute(meta['exists_sql'])
            obj = cur.fetchone()[0]
            if obj:
                path = os.path.join(OUTPUT_DIR, meta['filename'])
                try:
                    count = write_csv(cur, meta['sql'], path)
                    results[key] = {"path": path, "rows": count}
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    results[key] = {"path": path, "error": str(e)}
            else:
                results[key] = {"path": None, "rows": 0, "note": "object not present"}
        except Exception as e:
            results[key] = {"path": None, "error": str(e)}

    cur.close()
    conn.close()

    print("Audit complete:")
    for k, v in results.items():
        print(f"- {k}: {v}")


if __name__ == '__main__':
    main()

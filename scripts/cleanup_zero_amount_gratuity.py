import os
import sys
import psycopg2
from psycopg2.extras import DictCursor


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def main():
    apply = '--apply' in sys.argv
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)

        # Count target rows
        cur.execute(
            """
            SELECT COUNT(*)
            FROM charter_charges
            WHERE (description ILIKE '%gratuity%')
              AND COALESCE(amount, 0) = 0
              AND gratuity_type IS NOT NULL
            """
        )
        count = cur.fetchone()[0]
        print(f"Zero-amount 'gratuity' rows with gratuity_type set: {count}")

        # Preview sample
        cur.execute(
            """
            SELECT charge_id, charter_id, description, amount, gratuity_type
            FROM charter_charges
            WHERE (description ILIKE '%gratuity%')
              AND COALESCE(amount, 0) = 0
              AND gratuity_type IS NOT NULL
            ORDER BY charge_id
            LIMIT 25
            """
        )
        rows = cur.fetchall()
        for r in rows:
            print(f"charge_id={r['charge_id']} charter_id={r['charter_id']} amount={r['amount']} type={r['gratuity_type']} desc='{r['description'] or ''}'")

        if apply:
            cur.execute(
                """
                UPDATE charter_charges
                   SET gratuity_type = NULL,
                       gst_amount = NULL,
                       tax_rate = NULL
                 WHERE (description ILIKE '%gratuity%')
                   AND COALESCE(amount, 0) = 0
                   AND gratuity_type IS NOT NULL
                """
            )
            affected = cur.rowcount
            conn.commit()
            print(f"Applied cleanup. Rows updated: {affected}")
        else:
            print("Dry-run only. Use --apply to commit changes.")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

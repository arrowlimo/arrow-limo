import os
import psycopg2
from psycopg2.extras import DictCursor
from decimal import Decimal, ROUND_HALF_UP


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def money(x: Decimal) -> str:
    if x is None:
        x = Decimal('0')
    return f"{Decimal(str(x)).quantize(Decimal('0.01'), ROUND_HALF_UP):,.2f}"


def main():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=DictCursor)

        # Controlled classification total
        cur.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS total
            FROM charter_charges
            WHERE gratuity_type = 'controlled'
            """
        )
        class_cnt, class_total = cur.fetchone()

        # Description pattern total
        cur.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS total
            FROM charter_charges
            WHERE LOWER(description) LIKE '%gratuity%'
            """
        )
        desc_cnt, desc_total = cur.fetchone()

        # Lines classified controlled but description does NOT contain gratuity
        cur.execute(
            """
            SELECT charge_id, charter_id, description, amount
            FROM charter_charges
            WHERE gratuity_type = 'controlled'
              AND (description IS NULL OR LOWER(description) NOT LIKE '%gratuity%')
            ORDER BY charge_id
            LIMIT 50
            """
        )
        controlled_without_desc = cur.fetchall()

        # Lines with description containing gratuity but NOT classified controlled
        cur.execute(
            """
            SELECT charge_id, charter_id, description, amount
            FROM charter_charges
            WHERE LOWER(description) LIKE '%gratuity%'
              AND (gratuity_type IS NULL OR gratuity_type <> 'controlled')
            ORDER BY charge_id
            LIMIT 50
            """
        )
        desc_without_controlled = cur.fetchall()

        variance = Decimal(str(class_total)) - Decimal(str(desc_total))

        print("=== Gratuity Variance Audit ===")
        print(f"Classification total (gratuity_type='controlled'): {money(class_total)} (rows: {class_cnt})")
        print(f"Description pattern total (contains 'gratuity'): {money(desc_total)} (rows: {desc_cnt})")
        print(f"Variance (classified - description): {money(variance)}")
        print()
        print("Top examples: controlled but description lacks 'gratuity' (limit 50)")
        for r in controlled_without_desc:
            print(f"charge_id={r['charge_id']} charter_id={r['charter_id']} amount={money(r['amount'])} desc='{r['description'] or ''}'")
        print()
        print("Top examples: description has 'gratuity' but not classified controlled (limit 50)")
        for r in desc_without_controlled:
            print(f"charge_id={r['charge_id']} charter_id={r['charter_id']} amount={money(r['amount'])} desc='{r['description'] or ''}'")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

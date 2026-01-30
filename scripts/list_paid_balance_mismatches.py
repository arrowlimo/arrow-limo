"""
List charters with paid_amount vs sum(payments) or balance mismatches.

Mirrors verify_almsdata_integrity.py logic to show detailed rows for investigation.
"""
import os
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def columns(cur, table: str):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def main():
    conn = connect(); cur = conn.cursor()
    pcols = columns(cur, 'payments')
    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    if not amount_col:
        print('Required columns not found.')
        return

    # Paid_amount mismatches
    cur.execute(
        f"""
        WITH payment_sums AS (
          SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_number
        )
        SELECT c.reserve_number,
               ps.paid AS paid_sum,
               ROUND(COALESCE(c.paid_amount,0)::numeric,2) AS paid_field,
               ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
               ROUND(COALESCE(c.balance,0)::numeric,2) AS balance_field
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
        WHERE ROUND(COALESCE(ps.paid,0)::numeric,2) <> ROUND(COALESCE(c.paid_amount,0)::numeric,2)
        ORDER BY c.reserve_number
        """
    )
    paid_mismatches = cur.fetchall()

    # Balance mismatches
    cur.execute(
        f"""
        WITH payment_sums AS (
          SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
          FROM payments
          WHERE reserve_number IS NOT NULL
          GROUP BY reserve_number
        )
        SELECT c.reserve_number,
               ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
               COALESCE(ps.paid,0) AS paid_sum,
               ROUND(COALESCE(c.balance,0)::numeric,2) AS balance_field,
               (ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - COALESCE(ps.paid,0)) AS expected_balance
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
        WHERE (ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ROUND(COALESCE(ps.paid,0)::numeric,2))
              <> ROUND(COALESCE(c.balance,0)::numeric,2)
        ORDER BY c.reserve_number
        """
    )
    bal_mismatches = cur.fetchall()

    print(f"Paid_amount mismatches: {len(paid_mismatches)}")
    if paid_mismatches:
        print("\nreserve_number | paid_sum | paid_field | total_due | balance_field")
        for rn, ps, pf, td, bf in paid_mismatches:
            print(f"{rn} | {ps} | {pf} | {td} | {bf}")

    print(f"\nBalance mismatches: {len(bal_mismatches)}")
    if bal_mismatches:
        print("\nreserve_number | total_due | paid_sum | balance_field | expected_balance")
        for rn, td, ps, bf, eb in bal_mismatches:
            print(f"{rn} | {td} | {ps} | {bf} | {eb}")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()

#!/usr/bin/env python
"""
Add payment_method to charter_refunds and backfill using available linkage:
- If column missing: ALTER TABLE to add VARCHAR(50)
- Backfill priority:
  1) Join payments on charter_refunds.payment_id -> payments.payment_method or qb_payment_type
  2) If square_payment_id not null -> 'Square'
  3) Keyword heuristics on description/reference/customer

Usage:
  python -X utf8 scripts/backfill_charter_refunds_payment_method.py        # dry run
  python -X utf8 scripts/backfill_charter_refunds_payment_method.py --write
"""
import argparse
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name=%s AND column_name=%s
        )
        """,
        (table, column),
    )
    return cur.fetchone()[0]


def ensure_column(cur):
    if not column_exists(cur, 'charter_refunds', 'payment_method'):
        cur.execute("ALTER TABLE charter_refunds ADD COLUMN payment_method VARCHAR(50)")
        return True
    return False


def backfill(cur, write=False):
    updated = 0

    # 1) From payments join (payment_id)
    cur.execute(
        """
        WITH src AS (
          SELECT r.id AS refund_id,
                 COALESCE(p.payment_method, p.qb_payment_type) AS method
          FROM charter_refunds r
          JOIN payments p ON p.payment_id = r.payment_id
          WHERE r.payment_id IS NOT NULL
        )
        UPDATE charter_refunds r
        SET payment_method = s.method
        FROM src s
        WHERE r.id = s.refund_id AND (r.payment_method IS NULL OR r.payment_method = '')
        RETURNING r.id
        """
    )
    rows = cur.fetchall()
    updated += len(rows)

    # 2) Square fallback (square_payment_id present)
    cur.execute(
        """
        UPDATE charter_refunds r
        SET payment_method = 'Square'
        WHERE (r.payment_method IS NULL OR r.payment_method = '')
          AND r.square_payment_id IS NOT NULL AND r.square_payment_id <> ''
        RETURNING r.id
        """
    )
    rows = cur.fetchall()
    updated += len(rows)

    # 3) Heuristics from description/reference/customer
    # Simple keywords
    patterns = [
        ("etransfer", "e-Transfer"),
        ("e-transfer", "e-Transfer"),
        ("interac", "e-Transfer"),
        ("visa", "Visa"),
        ("mastercard", "MasterCard"),
        ("amex", "Amex"),
        ("cheque", "Check"),
        ("check", "Check"),
        ("cash", "Cash"),
    ]
    total_heur = 0
    for needle, label in patterns:
        cur.execute(
            """
            UPDATE charter_refunds r
            SET payment_method = %s
            WHERE (r.payment_method IS NULL OR r.payment_method = '')
              AND (
                    LOWER(COALESCE(r.description,'')) LIKE %s
                 OR LOWER(COALESCE(r.reference,'')) LIKE %s
                 OR LOWER(COALESCE(r.customer,'')) LIKE %s
              )
            RETURNING r.id
            """,
            (label, f"%{needle}%", f"%{needle}%", f"%{needle}%"),
        )
        rows = cur.fetchall()
        total_heur += len(rows)
    updated += total_heur

    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill charter_refunds.payment_method")
    parser.add_argument("--write", action="store_true", help="Apply changes")
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    col_added = ensure_column(cur)
    if col_added:
        print("Added payment_method column to charter_refunds")

    # Run backfill steps
    updated = backfill(cur, write=args.write)
    print(f"Would update {updated} refund rows" if not args.write else f"Updated {updated} refund rows")

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

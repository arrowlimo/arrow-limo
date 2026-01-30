"""
Safely fix pre-2025 charter fields (dry-run by default).

Repairs for charters with inconsistencies BEFORE a cutoff date (default 2025-01-01):
- Recompute total_amount_due from SUM(charter_charges.amount) where mismatched
- Recompute paid_amount from SUM(payments by reserve_number)
- Recompute balance = total_amount_due - paid_amount

Rules:
- Join payments by reserve_number (business key)
- Read-only unless --write
- Optional --backup to snapshot rows being updated into charters_backup_YYYYMMDD_HHMMSS
"""
import os
import sys
import argparse
from datetime import datetime, date
import psycopg2


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def table_exists(cur, name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
        """,
        (name,)
    )
    return cur.fetchone()[0]


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


def parse_date(s: str) -> date:
    return datetime.fromisoformat(s).date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply fixes')
    ap.add_argument('--backup', action='store_true', help='Backup affected charters before update')
    ap.add_argument('--cutoff', default='2025-01-01', help='Cutoff date (YYYY-MM-DD), strictly before this date')
    args = ap.parse_args()

    cutoff = parse_date(args.cutoff)
    conn = connect()
    cur = conn.cursor()

    if not table_exists(cur, 'charters') or not table_exists(cur, 'payments'):
        print('Required tables not found (charters/payments).', file=sys.stderr)
        sys.exit(2)

    pcols = columns(cur, 'payments')
    ccols = columns(cur, 'charters')
    chg_exists = table_exists(cur, 'charter_charges')
    chg_cols = columns(cur, 'charter_charges') if chg_exists else []

    amount_col = 'amount' if 'amount' in pcols else ('payment_amount' if 'payment_amount' in pcols else None)
    date_col = None
    for c in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if c in pcols:
            date_col = c
            break
    charter_date_col = 'charter_date' if 'charter_date' in ccols else (
        'reservation_time' if 'reservation_time' in ccols else None
    )
    if not amount_col or not date_col or not charter_date_col:
        print('Missing critical columns for fix computation.', file=sys.stderr)
        sys.exit(2)

    # Build pre-cutoff payment sums by reserve_number
    cur.execute(
        f"""
        CREATE TEMP VIEW tmp_payment_sums AS
        SELECT reserve_number, ROUND(SUM(COALESCE({amount_col},0))::numeric,2) AS paid
        FROM payments
        WHERE reserve_number IS NOT NULL
          AND CAST({date_col} AS DATE) < %s
        GROUP BY reserve_number
        """,
        (cutoff,)
    )

    # Build pre-cutoff charges sums if available
    join_clause = None
    if chg_exists:
        if 'charter_id' in ccols and 'charter_id' in chg_cols:
            join_clause = 'cc.charter_id = c.charter_id'
        elif 'reserve_number' in ccols and 'reserve_number' in chg_cols:
            join_clause = 'cc.reserve_number = c.reserve_number'

    # Determine affected charters
    # We compute authoritative totals and paid from the sums, then compare
    cur.execute(
        f"""
        WITH c AS (
          SELECT c.reserve_number,
                 CAST(c.{charter_date_col} AS DATE) AS cdate,
                 ROUND(COALESCE(c.total_amount_due,0)::numeric,2) AS total_due,
                 ROUND(COALESCE(c.paid_amount,0)::numeric,2) AS paid_field,
                 ROUND(COALESCE(c.balance,0)::numeric,2) AS bal_field
          FROM charters c
          WHERE CAST(c.{charter_date_col} AS DATE) < %s
        ),
        charges AS (
          SELECT c.reserve_number,
                 ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) AS charges_sum
          FROM charters c
          LEFT JOIN charter_charges cc ON {join_clause if join_clause else 'false'}
          WHERE CAST(c.{charter_date_col} AS DATE) < %s
          GROUP BY c.reserve_number
        ),
        pay AS (
          SELECT * FROM tmp_payment_sums
        )
        SELECT c.reserve_number,
               COALESCE(charges.charges_sum, c.total_due) AS authoritative_total,
               COALESCE(pay.paid, 0) AS authoritative_paid,
               c.total_due, c.paid_field, c.bal_field
        FROM c
        LEFT JOIN charges ON charges.reserve_number = c.reserve_number
        LEFT JOIN pay ON pay.reserve_number = c.reserve_number
        WHERE (COALESCE(charges.charges_sum, c.total_due) <> c.total_due)
           OR (COALESCE(pay.paid,0) <> c.paid_field)
           OR (ROUND((COALESCE(charges.charges_sum, c.total_due) - COALESCE(pay.paid,0))::numeric,2) <> c.bal_field)
        """,
        (cutoff, cutoff)
    )
    affected = cur.fetchall()
    print(f"Charters to fix (pre-{cutoff.isoformat()}): {len(affected)}")
    for row in affected[:10]:
        rn, auth_total, auth_paid, total_due, paid_field, bal_field = row
        exp_balance = round(float(auth_total) - float(auth_paid), 2)
        print(f"  {rn}: total {total_due}→{auth_total}, paid {paid_field}→{auth_paid}, bal {bal_field}→{exp_balance}")

    if not args.write:
        conn.rollback()
        print("Dry-run complete. No changes applied.")
        return

    # Backup if requested
    if args.backup and affected:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"charters_backup_{ts}"
        cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM charters WHERE reserve_number = ANY(%s)", ([r[0] for r in affected],))
        print(f"Backup created: {backup_name} ({cur.rowcount} rows)")

    # Apply updates in two passes to minimize recalculation issues
    # Pass 1: total_amount_due from charges where mismatched
        if chg_exists and join_clause:
                cur.execute(
                        f"""
                        WITH charges AS (
                            SELECT c.reserve_number,
                                         ROUND(COALESCE(SUM(cc.amount),0)::numeric,2) AS charges_sum
                            FROM charters c
                            LEFT JOIN charter_charges cc ON {join_clause}
                            WHERE CAST(c.{charter_date_col} AS DATE) < %s
                            GROUP BY c.reserve_number
                        )
                        UPDATE charters c
                        SET total_amount_due = ch.charges_sum
                        FROM charges ch
                        WHERE c.reserve_number = ch.reserve_number
                            AND ch.charges_sum > 0
                            AND ROUND(COALESCE(c.total_amount_due,0)::numeric,2) <> ch.charges_sum
                        """,
                        (cutoff,)
                )
                print(f"Updated total_amount_due: {cur.rowcount} rows (only where charges_sum > 0)")

    # Pass 2: paid_amount and balance from payment sums
        cur.execute(
                f"""
                WITH payment_sums AS (
                    SELECT reserve_number, ROUND(SUM(COALESCE(amount, payment_amount, 0))::numeric, 2) AS actual_paid
                    FROM payments
                    WHERE reserve_number IS NOT NULL
                    GROUP BY reserve_number
                )
                UPDATE charters c
                SET paid_amount = ps.actual_paid,
                        balance = ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ps.actual_paid
                FROM payment_sums ps
                WHERE c.reserve_number = ps.reserve_number
                    AND CAST(c.{charter_date_col} AS DATE) < %s
                    AND (
                        ROUND(COALESCE(c.paid_amount,0)::numeric,2) <> ps.actual_paid OR
                        ROUND(COALESCE(c.balance,0)::numeric,2) <> (ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - ps.actual_paid)
                    )
                """,
                (cutoff,)
        )
    print(f"Updated paid_amount/balance: {cur.rowcount} rows")

    conn.commit()
    print("Fix applied.")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Fix failed: {e}", file=sys.stderr)
        sys.exit(2)

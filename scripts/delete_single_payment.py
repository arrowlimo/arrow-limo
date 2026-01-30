"""
Safely delete a single payment by payment_id with backups, FK cleanup, and audit.

Usage:
  python -X utf8 scripts/delete_single_payment.py --payment-id 71882 --write --override-key ALLOW_DELETE_PAYMENTS_YYYYMMDD

Steps:
1) Protection check (requires override key in write mode)
2) Lookup the payment, capture reserve_number and key fields
3) Backup dependent rows (FKs referencing payments.payment_id) and delete them
4) Backup the payment row and delete it
5) Recalculate charters.paid_amount and balance via reserve_number
6) Log deletion to deletion_audit.log
"""
import os
import sys
import argparse
from datetime import datetime
import psycopg2
from table_protection import protect_deletion, create_backup_before_delete, require_write_mode, log_deletion_audit


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def get_fk_references(cur, schema: str, table: str):
    cur.execute(
        """
        SELECT
            tc.table_name AS fk_table,
            kcu.column_name AS fk_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_schema = %s
          AND ccu.table_name = %s
          AND ccu.column_name = 'payment_id'
        ORDER BY fk_table
        """,
        (schema, table)
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--payment-id', type=int, required=True, help='payment_id to delete')
    ap.add_argument('--write', action='store_true', help='Apply deletion (default dry-run)')
    ap.add_argument('--override-key', help='Override key for deleting from protected payments table')
    args = ap.parse_args()

    conn = connect(); conn.autocommit = False
    cur = conn.cursor()

    # Protection
    protect_deletion('payments', dry_run=not args.write, override_key=args.override_key)

    # Lookup payment
    cur.execute(
        """
        SELECT payment_id, reserve_number, COALESCE(amount, payment_amount) AS amount,
               CAST(COALESCE(payment_date, created_at, last_updated, updated_at) AS DATE) AS pdate,
               COALESCE(payment_method,'') AS payment_method,
               COALESCE(payment_key,'') AS payment_key
        FROM payments
        WHERE payment_id = %s
        """,
        (args.payment_id,)
    )
    row = cur.fetchone()
    if not row:
        print(f"Payment not found: payment_id={args.payment_id}")
        conn.rollback(); cur.close(); conn.close(); return

    payment_id, reserve_number, amount, pdate, method, pkey = row
    print(f"Target: payment_id={payment_id} reserve_number={reserve_number} amount={amount} date={pdate} method={method} key={pkey}")

    # Dry-run path: enumerate dependencies and exit
    fk_refs = get_fk_references(cur, 'public', 'payments')
    dep_counts = []
    for fk_table, fk_col in fk_refs:
        cur.execute(f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = %s", (payment_id,))
        dep_counts.append((fk_table, fk_col, cur.fetchone()[0]))

    if not require_write_mode(args):
        print("Dependent rows:")
        for fk_table, fk_col, cnt in dep_counts:
            print(f" - {fk_table}.{fk_col}: {cnt}")
        conn.rollback(); cur.close(); conn.close(); return

    try:
        # Backup and delete dependents
        for fk_table, fk_col, cnt in dep_counts:
            if cnt <= 0:
                continue
            create_backup_before_delete(cur, fk_table, condition=f"{fk_col} = {payment_id}")
            cur.execute(f"DELETE FROM {fk_table} WHERE {fk_col} = %s", (payment_id,))
            print(f"Deleted {cur.rowcount} rows from {fk_table}")

        # Backup and delete payment
        create_backup_before_delete(cur, 'payments', condition=f"payment_id = {payment_id}")
        cur.execute("DELETE FROM payments WHERE payment_id = %s", (payment_id,))
        deleted = cur.rowcount
        print(f"Deleted {deleted} row from payments (payment_id={payment_id})")

        # Recalculate charters by reserve_number business key
        cur.execute(
            """
            WITH payment_sums AS (
                SELECT reserve_number,
                       ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number IS NOT NULL
                GROUP BY reserve_number
            )
            UPDATE charters c
            SET paid_amount = COALESCE(ps.actual_paid, 0),
                balance = ROUND(COALESCE(c.total_amount_due,0)::numeric,2) - COALESCE(ps.actual_paid, 0)
            FROM payment_sums ps
            WHERE c.reserve_number = ps.reserve_number
            """
        )
        conn.commit()

        # Audit log
        log_deletion_audit('payments', deleted, condition=f"payment_id = {payment_id}")
        print("Deletion applied and audit logged.")

    except Exception as e:
        conn.rollback()
        print(f"Failed during deletion: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    main()

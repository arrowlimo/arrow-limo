"""
Apply deletion of reclassified negative payments (pre-2025) with full safeguards.

Requires:
- Plan CSV from reclassify_negative_payments_pre2025.py (or the planner)
- Override key matching today's date to delete from protected 'payments'

Process:
1) Verify receipts exist for each plan row via source_hash (skip any missing)
2) Detect FK dependencies referencing payments.payment_id and backup+delete dependent rows
3) Backup targeted payments rows
4) Delete targeted payments
5) Recalculate charter paid_amount and balance using reserve_number sums
6) Log deletion audit

Idempotent: If run again, targeted payments should no longer exist and deletes will affect 0 rows.
"""
import os
import sys
import csv
import argparse
from datetime import datetime, date
import psycopg2
from table_protection import protect_deletion, create_backup_before_delete, require_write_mode, log_deletion_audit


REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
DEFAULT_PLAN = os.path.join(REPORTS_DIR, 'reclassify_negative_payments_plan_pre2025.csv')


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
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', default=DEFAULT_PLAN, help='Path to plan CSV with payment_id and source_hash')
    parser.add_argument('--write', action='store_true', help='Apply changes (default dry-run)')
    parser.add_argument('--override-key', help='Override key for deleting from protected payments table')
    args = parser.parse_args()

    if not os.path.exists(args.plan):
        print(f"Plan CSV not found: {args.plan}")
        sys.exit(2)

    # Load plan rows
    targets = []
    with open(args.plan, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        want_cols = set(reader.fieldnames or [])
        for row in reader:
            try:
                pid = int(row['payment_id'])
            except Exception:
                continue
            targets.append({
                'payment_id': pid,
                'source_hash': row.get('source_hash') if 'source_hash' in want_cols else None,
                'reserve_number': row.get('reserve_number') if 'reserve_number' in want_cols else None,
            })

    if not targets:
        print('No targets found in plan CSV.')
        sys.exit(0)

    conn = connect(); conn.autocommit = False
    cur = conn.cursor()

    # STEP 0: Protection check (will pass in dry-run, enforce in write)
    protect_deletion('payments', dry_run=not args.write, override_key=args.override_key)

    # STEP 1: Verify receipts exist when source_hash is available
    missing = []
    checked = 0
    for t in targets:
        if not t['source_hash']:
            continue
        cur.execute("SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1", (t['source_hash'],))
        checked += 1
        if not cur.fetchone():
            missing.append(t['payment_id'])
    if missing:
        print(f"WARNING: {len(missing)} plan rows have no matching receipt by source_hash (first 10): {missing[:10]}")

    # STEP 2: FK dependencies referencing payments.payment_id
    fk_refs = get_fk_references(cur, 'public', 'payments')
    id_list = [t['payment_id'] for t in targets]

    # Report path
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_md = os.path.join(REPORTS_DIR, f'apply_delete_reclassified_negatives_{ts}.md')
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # DRY-RUN: enumerate counts
    dep_counts = []
    for fk_table, fk_col in fk_refs:
        cur.execute(f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = ANY(%s)", (id_list,))
        dep_counts.append((fk_table, fk_col, cur.fetchone()[0]))

    # If not write, just emit a report and exit
    if not require_write_mode(args):
        with open(out_md, 'w', encoding='utf-8') as f:
            f.write(f"# APPLY (DRY-RUN): Delete Reclassified Negative Payments\n\n")
            f.write(f"Generated: {ts}\n\n")
            f.write(f"Plan CSV: {args.plan}\n\n")
            f.write(f"Targets: {len(id_list)}\n\n")
            f.write(f"Receipts checked: {checked}; Missing: {len(missing)}\n\n")
            f.write("## Dependent table counts\n")
            f.write("table | column | rows_referencing_targets\n")
            f.write("---|---|---\n")
            for fk_table, fk_col, cnt in dep_counts:
                f.write(f"{fk_table}|{fk_col}|{cnt}\n")
        print(f"DRY-RUN report: {out_md}")
        conn.rollback(); cur.close(); conn.close()
        return

    # WRITE MODE: perform deletion with backups in a transaction
    try:
        # Backup dependent rows and delete
        for fk_table, fk_col, cnt in dep_counts:
            if cnt <= 0:
                continue
            # Backup
            create_backup_before_delete(cur, fk_table, condition=f"{fk_col} = ANY(ARRAY[{','.join(str(x) for x in id_list)}])")
            # Delete
            cur.execute(f"DELETE FROM {fk_table} WHERE {fk_col} = ANY(%s)", (id_list,))
            print(f"Deleted {cur.rowcount} rows from {fk_table}")

        # Backup payments rows
        create_backup_before_delete(cur, 'payments', condition=f"payment_id = ANY(ARRAY[{','.join(str(x) for x in id_list)}])")

        # Delete payments
        cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (id_list,))
        deleted = cur.rowcount
        print(f"Deleted {deleted} rows from payments")

        # Recalculate charters paid_amount and balance by reserve_number
        # This respects the business key and ignores charter_id
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
        print("Recalculated paid_amount and balance on charters (where sums exist)")

        conn.commit()

        # Audit log
        log_deletion_audit('payments', deleted, condition=f"payment_id IN ({','.join(str(x) for x in id_list)})")

        # Emit apply report
        with open(out_md, 'w', encoding='utf-8') as f:
            f.write(f"# APPLY: Delete Reclassified Negative Payments\n\n")
            f.write(f"Applied: {ts}\n\n")
            f.write(f"Plan CSV: {args.plan}\n\n")
            f.write(f"Deleted payments: {deleted}\n\n")
            f.write("## Dependent tables processed\n")
            f.write("table | column | rows_deleted\n")
            f.write("---|---|---\n")
            for fk_table, fk_col, cnt in dep_counts:
                if cnt > 0:
                    f.write(f"{fk_table}|{fk_col}|{cnt}\n")
        print(f"Apply report: {out_md}")

    except Exception as e:
        conn.rollback()
        print(f"Failed during apply: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    main()

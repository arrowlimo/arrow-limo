#!/usr/bin/env python3
"""
Delete ALL banking_transactions rows for Scotia account 903990106011 in 2012 (for re-ingest).

Safety:
  - Uses table_protection safeguards and requires override key for write mode
  - Creates a selective backup table before deletion
  - Dry-run by default
"""
from __future__ import annotations
import argparse
import os
import psycopg2
from table_protection import protect_deletion, create_backup_before_delete, require_write_mode, log_deletion_audit


def get_conn():
    host = os.environ.get('DB_HOST', 'localhost')
    dbname = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply deletion (default: dry-run)')
    ap.add_argument('--override-key', help='Override key required for protected table deletion')
    ap.add_argument('--account', default='903990106011', help='Target account_number to clean (default: Scotia)')
    ap.add_argument('--from-date', default='2012-01-01')
    ap.add_argument('--to-date', default='2012-12-31')
    args = ap.parse_args()

    table = 'banking_transactions'
    cond = (
        f"account_number = '{args.account}' AND "
        f"transaction_date >= '{args.from_date}' AND transaction_date <= '{args.to_date}'"
    )

    conn = get_conn(); conn.autocommit = False
    cur = conn.cursor()

    # Protection check
    protect_deletion(table, dry_run=not args.write, override_key=args.override_key)

    # Count rows to delete
    cur.execute(f"SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0) FROM {table} WHERE {cond}")
    count, sum_debits, sum_credits = cur.fetchone()
    print(f"Target rows: {count} | Debits sum: {sum_debits} | Credits sum: {sum_credits}")

    if not require_write_mode(args):
        cur.close(); conn.close(); return

    # Backup
    backup = create_backup_before_delete(cur, table, condition=cond)

    # Delete
    cur.execute(f"DELETE FROM {table} WHERE {cond}")
    deleted = cur.rowcount
    conn.commit()
    log_deletion_audit(table, deleted, condition=cond, script_name=os.path.basename(__file__))
    print(f"Deleted {deleted} rows from {table} (backup: {backup})")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()

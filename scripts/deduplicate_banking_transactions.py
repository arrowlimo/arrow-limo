#!/usr/bin/env python3
"""
Deduplicate banking_transactions for a given period and account(s).
- Scans records by source_hash within the selected months/accounts
- Proposes deletions (keep lowest transaction_id in each duplicate group)
- Dry-run by default: prints a report and writes CSV of candidates
- When --write is provided, uses table protection, creates a backup, deletes, and logs audit

Usage examples:
  python -X utf8 scripts/deduplicate_banking_transactions.py --year 2012 --months 1-5 --canonical 0228362,3648117
  python -X utf8 scripts/deduplicate_banking_transactions.py --year 2012 --months 1-5 --statements 00339-7461615,3648117 --dry-run
  python -X utf8 scripts/deduplicate_banking_transactions.py --year 2012 --months 5 --canonical 0228362 --write --override-key ALLOW_DELETE_BANKING_TRANSACTIONS_20251102
"""
import argparse
import csv
import os
from datetime import date, timedelta
from decimal import Decimal

import psycopg2

# Optional protection module per repo conventions
try:
    from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit
except Exception:
    protect_deletion = None
    create_backup_before_delete = None
    log_deletion_audit = None


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def find_account_by_statement_format(cur, statement_number):
    cur.execute(
        """
        SELECT canonical_account_number, notes
        FROM account_number_aliases
        WHERE statement_format = %s
        """,
        (statement_number,),
    )
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    # Fallback: maybe it's canonical
    cur.execute(
        """SELECT EXISTS (SELECT 1 FROM banking_transactions WHERE account_number = %s LIMIT 1)""",
        (statement_number,),
    )
    if cur.fetchone()[0]:
        return statement_number, '(assumed canonical)'
    return None, None


def ensure_source_hash(cur):
    """Verify source_hash column exists and is populated; populate nulls within scope later as needed."""
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='banking_transactions' AND column_name='source_hash'
        )
        """
    )
    return cur.fetchone()[0]


def collect_dupes(cur, canonical_accounts, months, year):
    results = []
    total_dupes = 0
    plan = []  # rows to delete
    for canonical in canonical_accounts:
        for m in months:
            ms, me = month_bounds(year, m)
            # Within this scope, find duplicate groups by source_hash (count>1)
            cur.execute(
                """
                SELECT source_hash, COUNT(*) AS cnt
                FROM banking_transactions
                WHERE account_number = %s
                  AND transaction_date BETWEEN %s AND %s
                  AND source_hash IS NOT NULL
                GROUP BY source_hash
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
                """,
                (canonical, ms, me),
            )
            groups = cur.fetchall()
            month_dupes = 0
            month_delete_rows = []
            for shash, cnt in groups:
                # fetch all rows in group to decide keeps/deletes
                cur.execute(
                    """
                    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
                    FROM banking_transactions
                    WHERE account_number = %s
                      AND transaction_date BETWEEN %s AND %s
                      AND source_hash = %s
                    ORDER BY transaction_id ASC
                    """,
                    (canonical, ms, me, shash),
                )
                rows = cur.fetchall()
                if not rows:
                    continue
                keep_id = rows[0][0]  # keep lowest transaction_id
                # all others are candidates to delete
                for (tid, tdate, desc, deb, cred, bal) in rows[1:]:
                    month_delete_rows.append((tid, tdate, desc, deb or Decimal('0'), cred or Decimal('0'), bal, canonical, ms, me, shash, keep_id))
            month_dupes = len(month_delete_rows)
            if month_dupes:
                plan.extend(month_delete_rows)
            results.append((canonical, m, ms, me, month_dupes))
            total_dupes += month_dupes
    return results, plan, total_dupes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2012)
    parser.add_argument('--months', type=str, default='1-5')
    parser.add_argument('--statements', type=str, default='00339-7461615,3648117')
    parser.add_argument('--canonical', type=str, default=None)
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--override-key', type=str, default=None)
    args = parser.parse_args()

    # Parse months
    months = []
    if '-' in args.months:
        a, b = args.months.split('-', 1)
        months = list(range(int(a), int(b) + 1))
    else:
        months = [int(x) for x in args.months.split(',') if x.strip()]

    conn = get_db_connection()
    cur = conn.cursor()

    # Resolve accounts
    canonical_accounts = []
    if args.canonical:
        canonical_accounts = [x.strip() for x in args.canonical.split(',') if x.strip()]
    else:
        for s in [x.strip() for x in args.statements.split(',') if x.strip()]:
            c, _ = find_account_by_statement_format(cur, s)
            if c:
                canonical_accounts.append(c)
    canonical_accounts = sorted(set(canonical_accounts))

    print('=' * 100)
    print(f'DEDUPLICATION PREVIEW - banking_transactions  Year={args.year} Months={args.months}')
    print('=' * 100)
    print(f'Accounts: {", ".join(canonical_accounts)}')

    has_hash = ensure_source_hash(cur)
    if not has_hash:
        print('[FAIL] source_hash column missing. Please run the schema fix script first.')
        return

    # Collect duplicates
    results, plan, total_dupes = collect_dupes(cur, canonical_accounts, months, args.year)

    # Summarize by account/month
    for canonical, m, ms, me, month_dupes in results:
        label = ms.strftime('%b %Y')
        note = 'no duplicates' if month_dupes == 0 else f'{month_dupes} duplicate rows to delete'
        print(f'- {canonical}  {label}: {note}')

    print('\nSummary:')
    print(f'  Total duplicate rows to delete: {total_dupes}')

    # Export plan CSV
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)
    out_csv = os.path.join(reports_dir, f'dupe_candidates_{args.year}_{args.months}.csv')
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['transaction_id', 'transaction_date', 'description', 'debit_amount', 'credit_amount', 'balance', 'account_number', 'scope_start', 'scope_end', 'source_hash', 'keep_transaction_id'])
        for row in plan:
            w.writerow(row)
    print(f'  Exported deletion plan: {out_csv}')

    if not args.write:
        print('\nDry-run only. Re-run with --write and a valid override key to apply deletions.')
        cur.close(); conn.close(); return

    # Write path: require protection + override key
    if protect_deletion is None or create_backup_before_delete is None or log_deletion_audit is None:
        print('[FAIL] table_protection is not available. Cannot proceed with write mode safely.')
        cur.close(); conn.close(); return

    if not args.override_key:
        print('[FAIL] Missing --override-key. Required for protected deletion.')
        cur.close(); conn.close(); return

    # Check protection gate
    try:
        protect_deletion('banking_transactions', dry_run=False, override_key=args.override_key)
    except Exception as e:
        print(f'[FAIL] Protection check failed: {e}')
        cur.close(); conn.close(); return

    # Backup before delete within the scope condition
    # We'll delete by explicit transaction_id list; still create a backup snapshot
    ids_to_delete = [r[0] for r in plan]
    if not ids_to_delete:
        print('No duplicates to delete. Exiting.')
        cur.close(); conn.close(); return

    condition = f"transaction_id IN ({', '.join(str(i) for i in ids_to_delete)})"
    try:
        backup_name = create_backup_before_delete(cur, 'banking_transactions', condition=condition)
        print(f'  Backup created: {backup_name}')
    except Exception as e:
        print(f'[FAIL] Backup step failed: {e}')
        cur.close(); conn.close(); return

    # Perform batched deletions
    deleted = 0
    batch = 1000
    for i in range(0, len(ids_to_delete), batch):
        chunk = ids_to_delete[i:i+batch]
        cur.execute(f"DELETE FROM banking_transactions WHERE transaction_id = ANY(%s)", (chunk,))
        deleted += cur.rowcount
        conn.commit()
    log_deletion_audit('banking_transactions', deleted, condition=condition)
    print(f'[OK] Deleted {deleted} duplicate rows (kept lowest transaction_id per duplicate group).')

    cur.close(); conn.close()


if __name__ == '__main__':
    main()

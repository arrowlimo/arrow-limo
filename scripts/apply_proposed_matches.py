"""
Apply a small, high-confidence subset of proposed matches for unmatched payments.

Reads reports/proposed_matches_for_unmatched_pre2025.csv and:
- Filters to payment_ids that have exactly one proposed reserve_number (unique, conflict-free)
- Limits the number applied via --limit (default 5)
- Backs up targeted payments rows
- Updates payments.reserve_number for those payment_ids
- Recalculates charters.paid_amount and balance by reserve_number
- Writes a Markdown apply report

Use --write to apply; dry-run prints the plan and emits a report without changes.
"""
import os
import sys
import csv
import argparse
from datetime import datetime
import psycopg2


REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
PROPOSALS_CSV = os.path.join(REPORTS_DIR, 'proposed_matches_for_unmatched_pre2025.csv')


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def create_backup(cur, table: str, condition: str):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{table}_backup_before_update_{ts}"
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table} WHERE {condition}")
    cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
    cnt = cur.fetchone()[0]
    print(f"✓ Created backup: {backup_name} ({cnt} rows)")
    return backup_name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=5, help='Max number of matches to apply')
    ap.add_argument('--proposals', default=PROPOSALS_CSV, help='Path to proposals CSV')
    ap.add_argument('--write', action='store_true', help='Apply updates (default dry-run)')
    args = ap.parse_args()

    proposals_path = args.proposals
    if not os.path.exists(proposals_path):
        print(f"Proposals CSV not found: {proposals_path}")
        sys.exit(2)

    # Load proposals
    proposals = []
    with open(proposals_path, 'r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                proposals.append({
                    'payment_id': int(row['payment_id']),
                    'reserve_number': row['reserve_number'],
                    'confidence': int(row.get('confidence') or 0),
                })
            except Exception:
                continue

    if not proposals:
        print('No proposals found.')
        sys.exit(0)

    # Build unique map: only payment_ids with a single candidate
    by_pid = {}
    for p in proposals:
        by_pid.setdefault(p['payment_id'], set()).add(p['reserve_number'])
    unique = [(pid, list(rns)[0]) for pid, rns in by_pid.items() if len(rns) == 1]

    to_apply = unique[: args.limit]
    print(f"Unique proposals: {len(unique)}; Planning to apply: {len(to_apply)}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_md = os.path.join(REPORTS_DIR, f'apply_proposed_matches_{ts}.md')

    conn = connect(); conn.autocommit = False
    cur = conn.cursor()

    # Emit dry-run plan or apply
    try:
        if not args.write:
            with open(out_md, 'w', encoding='utf-8') as f:
                f.write(f"# APPLY (DRY-RUN): Proposed Matches for Unmatched Payments\n\n")
                f.write(f"Generated: {ts}\n\n")
                f.write(f"Planned updates (limit {args.limit}): {len(to_apply)}\n\n")
                f.write("payment_id | reserve_number\n")
                f.write("---|---\n")
                for pid, rn in to_apply:
                    f.write(f"{pid}|{rn}\n")
            print(f"DRY-RUN report: {out_md}")
            conn.rollback(); cur.close(); conn.close(); return

        # Backup payments rows to be updated
        id_list = [pid for pid, _ in to_apply]
        if id_list:
            create_backup(cur, 'payments', condition=f"payment_id = ANY(ARRAY[{','.join(str(x) for x in id_list)}])")

        # Apply updates
        updated = 0
        for pid, rn in to_apply:
            cur.execute("UPDATE payments SET reserve_number = %s WHERE payment_id = %s", (rn, pid))
            updated += cur.rowcount

        # Recalculate charters
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

        with open(out_md, 'w', encoding='utf-8') as f:
            f.write(f"# APPLY: Proposed Matches for Unmatched Payments\n\n")
            f.write(f"Applied: {ts}\n\n")
            f.write(f"Updated payments rows: {updated}\n\n")
            f.write("payment_id | reserve_number\n")
            f.write("---|---\n")
            for pid, rn in to_apply:
                f.write(f"{pid}|{rn}\n")

        print(f"Apply report: {out_md}")
    except Exception as e:
        conn.rollback()
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    main()

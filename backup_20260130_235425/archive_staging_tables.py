import os
import argparse
import psycopg2
from datetime import datetime

TABLES_TO_ARCHIVE = [
    'lms_staging_customer',
    'lms_staging_payment',
    'lms_staging_reserve',
    'staging_receipts_raw',
    'staging_scotia_2012_verified',
    'staging_banking_pdf_transactions',
]

SUFFIX = datetime.now().strftime('%Y%m%d')  # e.g., 20251109
SUFFIX = f"_archived_{SUFFIX}"  # lower-case for consistency


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def table_exists(cur, name: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (name,))
    return cur.fetchone()[0] is not None


def main():
    parser = argparse.ArgumentParser(description='Archive staging tables by renaming with dated suffix.')
    parser.add_argument('--apply', action='store_true', help='Actually perform the rename (default is dry-run).')
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    archived = []
    skipped = []
    missing = []

    print("=" * 80)
    print("ARCHIVE STAGING TABLES")
    print("=" * 80)
    print(f"Suffix to apply: {SUFFIX}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}\n")

    for t in TABLES_TO_ARCHIVE:
        target = f"{t}{SUFFIX}"
        print(f"Checking: {t} -> {target}")

        if not table_exists(cur, t):
            print(f"  - SKIP (missing)")
            missing.append(t)
            continue
        if table_exists(cur, target):
            print(f"  - SKIP (already archived as {target})")
            skipped.append(t)
            continue

        # Optional: get row count (for log)
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        row_count = cur.fetchone()[0]
        print(f"  - Rows: {row_count:,}")

        if args.apply:
            cur.execute(f"ALTER TABLE {t} RENAME TO {target}")
            archived.append((t, target, row_count))
            conn.commit()
            print(f"  - RENAMED")
        else:
            print(f"  - WOULD RENAME (dry-run)")
        print()

    print("\n" + "-" * 80)
    print("RESULTS")
    print("-" * 80)
    if archived:
        print("Archived (renamed):")
        for t, target, rc in archived:
            print(f"  {t} -> {target} ({rc:,} rows)")
    else:
        print("No tables archived in this run.")

    if skipped:
        print("\nSkipped (already archived):")
        for t in skipped:
            print(f"  {t}")

    if missing:
        print("\nMissing (not found):")
        for t in missing:
            print(f"  {t}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()

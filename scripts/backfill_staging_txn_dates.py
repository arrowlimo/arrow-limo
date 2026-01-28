#!/usr/bin/env python3
"""
Enhanced parser pass to backfill txn_date for staging rows missing it.
Strategy:
- For xlsx/xls: extract date from filename (e.g., "2024-07 Driver Pay.xlsx") or sheet names.
- For PDF: extract from filename or metadata.
- Update existing staging_driver_pay rows with inferred txn_date where NULL.

Usage:
  python scripts/backfill_staging_txn_dates.py --dry-run
  python scripts/backfill_staging_txn_dates.py --apply
"""
import os
import re
import argparse
from pathlib import Path
from datetime import datetime
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')


def connect_db():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD)


# Patterns for date extraction from filenames
DATE_PATTERNS = [
    (re.compile(r'(\d{4})[-_](\d{2})[-_](\d{2})'), '%Y-%m-%d'),  # 2024-07-15
    (re.compile(r'(\d{4})[-_](\d{2})'), '%Y-%m'),  # 2024-07 -> first of month
    (re.compile(r'([A-Z][a-z]{2,8})\s+(\d{4})'), '%B %Y'),  # July 2024
    (re.compile(r'(\d{2})[-_](\d{2})[-_](\d{4})'), '%m-%d-%Y'),  # 07-15-2024
]


def extract_date_from_path(file_path: str):
    """Try to extract a date from the file path or name."""
    for pat, fmt in DATE_PATTERNS:
        m = pat.search(file_path)
        if m:
            try:
                if fmt == '%Y-%m':
                    return datetime.strptime(f"{m.group(1)}-{m.group(2)}-01", '%Y-%m-%d').date()
                elif fmt == '%B %Y':
                    return datetime.strptime(f"{m.group(1)} {m.group(2)}", '%B %Y').replace(day=1).date()
                else:
                    return datetime.strptime(m.group(0), fmt).date()
            except Exception:
                continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Show what would be updated without applying')
    ap.add_argument('--apply', action='store_true', help='Apply the updates')
    ap.add_argument('--limit', type=int, default=10000, help='Limit files to process (default 10000)')
    args = ap.parse_args()

    if not args.dry_run and not args.apply:
        ap.error('Specify --dry-run or --apply')

    conn = connect_db()
    updated_rows = 0
    files_with_updates = 0

    try:
        with conn:
            with conn.cursor() as cur:
                # Get files with rows missing txn_date
                cur.execute(
                    """
                    SELECT f.id, f.file_path, COUNT(*) AS missing_date_rows
                    FROM staging_driver_pay_files f
                    JOIN staging_driver_pay p ON p.file_id = f.id
                    WHERE p.txn_date IS NULL
                    GROUP BY f.id, f.file_path
                    ORDER BY missing_date_rows DESC
                    LIMIT %s
                    """,
                    (args.limit,)
                )
                files = cur.fetchall()
                print(f"Found {len(files):,} files with rows missing txn_date")

                for file_id, file_path, missing_count in files:
                    inferred_date = extract_date_from_path(file_path)
                    if not inferred_date:
                        continue
                    if args.dry_run:
                        print(f"[DRY-RUN] {file_path} -> {inferred_date} ({missing_count} rows)")
                        files_with_updates += 1
                        updated_rows += missing_count
                    else:
                        cur.execute(
                            """
                            UPDATE staging_driver_pay
                            SET txn_date = %s
                            WHERE file_id = %s AND txn_date IS NULL
                            """,
                            (inferred_date, file_id)
                        )
                        if cur.rowcount > 0:
                            print(f"[UPDATED] {file_path} -> {inferred_date} ({cur.rowcount} rows)")
                            files_with_updates += 1
                            updated_rows += cur.rowcount

                if not args.dry_run:
                    conn.commit()
                print(f"\nSummary: {files_with_updates:,} files, {updated_rows:,} rows {'would be updated' if args.dry_run else 'updated'}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

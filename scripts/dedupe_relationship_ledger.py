#!/usr/bin/env python3
"""
Remove duplicate (banking_transaction_id, receipt_id) pairs from banking_receipt_matching_ledger.

Safety:
- Default is --dry-run (no changes). Use --write to apply.
- Keeps the lowest `id` per duplicate pair; deletes extras.
- Commits on success; rollbacks on exceptions.
"""

import argparse
import os
import sys
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def connect():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    parser = argparse.ArgumentParser(description="Deduplicate ledger pairs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--write", action="store_true", help="Apply changes to the database")
    args = parser.parse_args()

    if not args.write:
        args.dry_run = True

    conn = connect()
    cur = conn.cursor()

    # Count duplicate pairs
    cur.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT banking_transaction_id, receipt_id, COUNT(*) AS c
          FROM banking_receipt_matching_ledger
          WHERE banking_transaction_id IS NOT NULL AND receipt_id IS NOT NULL
          GROUP BY banking_transaction_id, receipt_id
          HAVING COUNT(*) > 1
        ) dup
        """
    )
    dup_pairs = cur.fetchone()[0]
    print(f"Duplicate pairs: {dup_pairs:,d}")

    # Show sample
    cur.execute(
        """
        SELECT banking_transaction_id, receipt_id, COUNT(*) AS c
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IS NOT NULL AND receipt_id IS NOT NULL
        GROUP BY banking_transaction_id, receipt_id
        HAVING COUNT(*) > 1
        ORDER BY c DESC
        LIMIT 10
        """
    )
    sample = cur.fetchall()
    if sample:
        print("Sample (up to 10):")
        for bt_id, r_id, c in sample:
            print(f"  banking_transaction_id={bt_id} receipt_id={r_id} count={c}")

    if args.dry_run:
        print("\nDry-run: no changes applied.")
        conn.close()
        return

    try:
        cur.execute(
            """
            DELETE FROM banking_receipt_matching_ledger brml
            USING (
              SELECT banking_transaction_id, receipt_id, MIN(id) AS keep_id
              FROM banking_receipt_matching_ledger
              WHERE banking_transaction_id IS NOT NULL AND receipt_id IS NOT NULL
              GROUP BY banking_transaction_id, receipt_id
              HAVING COUNT(*) > 1
            ) dups
            WHERE brml.banking_transaction_id = dups.banking_transaction_id
              AND brml.receipt_id = dups.receipt_id
              AND brml.id <> dups.keep_id
            """
        )
        deleted = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        print(f"Committed dedupe: {deleted:,d} rows deleted.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during dedupe, rolled back: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

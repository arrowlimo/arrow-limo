#!/usr/bin/env python3
"""
Fix mismatches where receipts.banking_transaction_id differs from 
banking_receipt_matching_ledger.banking_transaction_id.

Strategy (safe):
- Ensure the correct pair (receipt_id, receipts.banking_transaction_id) exists; insert if missing.
- Update all ledger rows for that receipt that have a different banking_transaction_id to the correct one.
- This may create temporary duplicates; run dedupe after to collapse to one.

Safety:
- Default is --dry-run. Use --write to apply.
- Commits on success, rollback on error.
"""

import argparse
import os
import sys
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def connect():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    parser = argparse.ArgumentParser(description="Fix mismatched ledger links")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--write", action="store_true", help="Apply changes to the database")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit of receipts to fix")
    args = parser.parse_args()

    if not args.write:
        args.dry_run = True

    conn = connect()
    cur = conn.cursor()

    # Count mismatches
    cur.execute(
        """
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger brml
        JOIN receipts r ON r.receipt_id = brml.receipt_id
        WHERE r.banking_transaction_id IS NOT NULL
          AND brml.banking_transaction_id IS NOT NULL
          AND r.banking_transaction_id <> brml.banking_transaction_id
        """
    )
    mismatches = cur.fetchone()[0]
    print(f"Mismatched links: {mismatches:,d}")

    # Show sample receipts to fix
    cur.execute(
        """
        SELECT DISTINCT r.receipt_id, r.banking_transaction_id AS correct_btid
        FROM banking_receipt_matching_ledger brml
        JOIN receipts r ON r.receipt_id = brml.receipt_id
        WHERE r.banking_transaction_id IS NOT NULL
          AND brml.banking_transaction_id IS NOT NULL
          AND r.banking_transaction_id <> brml.banking_transaction_id
        ORDER BY r.receipt_id DESC
        LIMIT 10
        """
    )
    sample = cur.fetchall()
    if sample:
        print("Sample receipts to fix (up to 10):")
        for rid, btid in sample:
            print(f"  receipt_id={rid} correct_btid={btid}")

    if args.dry_run:
        print("\nDry-run: no changes applied.")
        conn.close()
        return

    try:
        # Build CTE of target receipts to limit scope if requested
        limit = int(args.limit) if args.limit and args.limit > 0 else None

        # 1) Ensure correct pair exists (insert missing correct rows)
        insert_sql = """
            WITH targets AS (
              SELECT DISTINCT r.receipt_id, r.banking_transaction_id AS correct_btid
              FROM banking_receipt_matching_ledger brml
              JOIN receipts r ON r.receipt_id = brml.receipt_id
              WHERE r.banking_transaction_id IS NOT NULL
                AND brml.banking_transaction_id IS NOT NULL
                AND r.banking_transaction_id <> brml.banking_transaction_id
              ORDER BY r.receipt_id DESC
              {limit_clause}
            )
            INSERT INTO banking_receipt_matching_ledger (
                banking_transaction_id, receipt_id, match_date,
                match_type, match_status, match_confidence, notes, created_by
            )
            SELECT t.correct_btid, r.receipt_id,
                   COALESCE(r.receipt_date, NOW()),
                   'auto_generated', 'matched', 'auto',
                   'Fix mismatch: ensure correct pair exists', 'system'
            FROM targets t
            JOIN receipts r ON r.receipt_id = t.receipt_id
            WHERE NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger brml2
                WHERE brml2.receipt_id = r.receipt_id
                  AND brml2.banking_transaction_id = r.banking_transaction_id
            )
        """

        # Render limit clause for CTE
        insert_sql = insert_sql.replace("{limit_clause}", f"LIMIT {limit}" if limit else "")
        cur.execute(insert_sql)
        inserted = cur.rowcount if cur.rowcount is not None else 0
        print(f"Inserted correct pairs: {inserted:,d}")

        # 2) Update mismatched rows to the correct banking_transaction_id
        update_sql = """
            WITH targets AS (
              SELECT DISTINCT r.receipt_id, r.banking_transaction_id AS correct_btid
              FROM banking_receipt_matching_ledger brml
              JOIN receipts r ON r.receipt_id = brml.receipt_id
              WHERE r.banking_transaction_id IS NOT NULL
                AND brml.banking_transaction_id IS NOT NULL
                AND r.banking_transaction_id <> brml.banking_transaction_id
              ORDER BY r.receipt_id DESC
              {limit_clause}
            )
            UPDATE banking_receipt_matching_ledger brml
            SET banking_transaction_id = t.correct_btid,
                notes = COALESCE(brml.notes, '') || ' | Fix mismatch: updated to receipt value'
            FROM targets t
            WHERE brml.receipt_id = t.receipt_id
              AND brml.banking_transaction_id IS NOT NULL
              AND brml.banking_transaction_id <> t.correct_btid
        """

        update_sql = update_sql.replace("{limit_clause}", f"LIMIT {limit}" if limit else "")
        cur.execute(update_sql)
        updated = cur.rowcount if cur.rowcount is not None else 0
        print(f"Updated mismatched rows: {updated:,d}")

        conn.commit()
        print("Committed mismatch fixes.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during mismatch fix, rolled back: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Backfill missing rows in banking_receipt_matching_ledger based on receipts.banking_transaction_id.

Safety:
- Default is --dry-run (no changes). Use --write to apply.
- Idempotent insert pattern via WHERE NOT EXISTS.
- Commits on success; rollbacks on exceptions.

Notes:
- match_type: 'auto_generated'
- match_status: 'matched'
- match_date: banking_transactions.transaction_date if available, else receipts.receipt_date or NOW()
- created_by: 'system'
"""

import argparse
import os
import sys
import datetime
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def connect():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    parser = argparse.ArgumentParser(description="Backfill missing ledger entries from receipts")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--write", action="store_true", help="Apply changes to the database")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for write mode (0 = all)")
    args = parser.parse_args()

    if not args.write:
        args.dry_run = True

    conn = connect()
    cur = conn.cursor()

    # Count missing ledger entries
    cur.execute(
        """
        SELECT COUNT(*)
        FROM receipts r
        WHERE r.banking_transaction_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brml
            WHERE brml.receipt_id = r.receipt_id
              AND brml.banking_transaction_id = r.banking_transaction_id
          )
        """
    )
    missing_count = cur.fetchone()[0]

    print(f"Missing ledger entries to backfill: {missing_count:,d}")

    # Show sample
    cur.execute(
        """
        SELECT r.receipt_id, r.vendor_name, r.receipt_date, r.gross_amount, r.banking_transaction_id
        FROM receipts r
        WHERE r.banking_transaction_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brml
            WHERE brml.receipt_id = r.receipt_id
              AND brml.banking_transaction_id = r.banking_transaction_id
          )
        ORDER BY r.receipt_date DESC
        LIMIT 10
        """
    )
    sample = cur.fetchall()
    if sample:
        print("Sample (up to 10):")
        for row in sample:
            print(f"  receipt {row[0]} | {row[1]} | {row[2]} | ${row[3]:,.2f} | banking_transaction_id={row[4]}")

    if args.dry_run:
        print("\nDry-run: no changes applied.")
        conn.close()
        return

    # Write mode: backfill
    try:
        # Optional limit
        limit_clause = ""
        if args.limit and args.limit > 0:
            limit_clause = f"LIMIT {int(args.limit)}"

        # Insert using SELECT with WHERE NOT EXISTS to be idempotent
        insert_sql = f"""
            INSERT INTO banking_receipt_matching_ledger (
                banking_transaction_id, receipt_id, match_date,
                match_type, match_status, match_confidence, notes, created_by
            )
            SELECT 
                r.banking_transaction_id,
                r.receipt_id,
                COALESCE(bt.transaction_date, r.receipt_date, NOW()),
                'auto_generated', 'matched', 'auto',
                'Backfill from receipts.banking_transaction_id', 'system'
            FROM receipts r
            LEFT JOIN banking_transactions bt 
              ON bt.transaction_id = r.banking_transaction_id
            WHERE r.banking_transaction_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger brml
                WHERE brml.receipt_id = r.receipt_id
                  AND brml.banking_transaction_id = r.banking_transaction_id
              )
            {limit_clause}
        """

        cur.execute(insert_sql)
        affected = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        print(f"Committed backfill: {affected:,d} rows inserted.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during backfill, rolled back: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Audit the banking_receipt_matching_ledger relationship table for validity.

Checks performed:
- Orphan links: ledger.banking_transaction_id missing in banking_transactions
- Orphan links: ledger.receipt_id missing in receipts
- Mismatched links: receipts.banking_transaction_id set and differs from ledger link
- Missing ledger entries: receipts with banking_transaction_id but no ledger row
- Duplicate links: multiple identical (banking_transaction_id, receipt_id) pairs
- Value distributions: match_status, match_type

Outputs a human-readable summary to console and writes a report under reports/.
"""

import os
import sys
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = os.path.join(REPORT_DIR, f"relationship_ledger_audit_{TIMESTAMP}.txt")


def connect():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def fetch_one(cur, query, params=None):
    cur.execute(query, params or ())
    row = cur.fetchone()
    return row[0] if row else 0


def fetch_all(cur, query, params=None):
    cur.execute(query, params or ())
    return cur.fetchall()


def write_lines(lines):
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def main():
    conn = connect()
    cur = conn.cursor()
    lines = []

    header = "=" * 78
    lines.append(header)
    lines.append("BANKING-RECEIPT MATCHING LEDGER AUDIT")
    lines.append(header)
    lines.append(f"Database: {DB_NAME} on {DB_HOST}")
    lines.append(f"Timestamp: {datetime.datetime.now().isoformat(timespec='seconds')}")

    # Totals
    total_ledger = fetch_one(cur, "SELECT COUNT(*) FROM banking_receipt_matching_ledger")
    total_receipts = fetch_one(cur, "SELECT COUNT(*) FROM receipts")
    total_banking = fetch_one(cur, "SELECT COUNT(*) FROM banking_transactions")
    lines.append("")
    lines.append(f"Rows: ledger={total_ledger:,d}, receipts={total_receipts:,d}, banking={total_banking:,d}")

    # Orphan banking_transaction_id
    orphan_banking = fetch_one(cur, """
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger brml
        WHERE brml.banking_transaction_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM banking_transactions bt
            WHERE bt.transaction_id = brml.banking_transaction_id
          )
    """)
    lines.append(f"Orphan banking links: {orphan_banking:,d}")

    # Orphan receipt_id
    orphan_receipts = fetch_one(cur, """
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger brml
        WHERE brml.receipt_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM receipts r
            WHERE r.receipt_id = brml.receipt_id
          )
    """)
    lines.append(f"Orphan receipt links: {orphan_receipts:,d}")

    # Mismatched receipt.banking_transaction_id vs ledger link
    mismatched_links = fetch_one(cur, """
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger brml
        JOIN receipts r ON r.receipt_id = brml.receipt_id
        WHERE r.banking_transaction_id IS NOT NULL
          AND brml.banking_transaction_id IS NOT NULL
          AND r.banking_transaction_id <> brml.banking_transaction_id
    """)
    lines.append(f"Mismatched links (receipt vs ledger): {mismatched_links:,d}")

    # Receipts with banking_transaction_id but no ledger entry
    missing_ledger = fetch_one(cur, """
        SELECT COUNT(*)
        FROM receipts r
        WHERE r.banking_transaction_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brml
            WHERE brml.receipt_id = r.receipt_id
              AND brml.banking_transaction_id = r.banking_transaction_id
          )
    """)
    lines.append(f"Receipts with banking_transaction_id but no ledger row: {missing_ledger:,d}")

    # Duplicate pairs
    duplicate_pairs = fetch_one(cur, """
        SELECT COUNT(*) FROM (
          SELECT banking_transaction_id, receipt_id, COUNT(*) AS c
          FROM banking_receipt_matching_ledger
          WHERE banking_transaction_id IS NOT NULL AND receipt_id IS NOT NULL
          GROUP BY banking_transaction_id, receipt_id
          HAVING COUNT(*) > 1
        ) dup
    """)
    lines.append(f"Duplicate (banking_transaction_id, receipt_id) pairs: {duplicate_pairs:,d}")

    # Distributions
    lines.append("")
    lines.append("Distributions:")
    status_dist = fetch_all(cur, """
        SELECT COALESCE(match_status, 'NULL') AS status, COUNT(*)
        FROM banking_receipt_matching_ledger
        GROUP BY COALESCE(match_status, 'NULL')
        ORDER BY 2 DESC
    """)
    lines.append("- match_status:")
    for status, count in status_dist:
        lines.append(f"  {status:20s} {count:10,d}")

    type_dist = fetch_all(cur, """
        SELECT COALESCE(match_type, 'NULL') AS type, COUNT(*)
        FROM banking_receipt_matching_ledger
        GROUP BY COALESCE(match_type, 'NULL')
        ORDER BY 2 DESC
    """)
    lines.append("- match_type:")
    for typ, count in type_dist:
        lines.append(f"  {typ:20s} {count:10,d}")

    # Samples: list up to 10 mismatches and 10 missing ledger
    lines.append("")
    lines.append("Samples:")
    mismatches = fetch_all(cur, """
        SELECT r.receipt_id, r.vendor_name, r.receipt_date, r.gross_amount,
               r.banking_transaction_id AS receipt_btid,
               brml.banking_transaction_id AS ledger_btid,
               brml.match_date, brml.match_status
        FROM banking_receipt_matching_ledger brml
        JOIN receipts r ON r.receipt_id = brml.receipt_id
        WHERE r.banking_transaction_id IS NOT NULL
          AND brml.banking_transaction_id IS NOT NULL
          AND r.banking_transaction_id <> brml.banking_transaction_id
        ORDER BY r.receipt_date DESC
        LIMIT 10
    """)
    if mismatches:
        lines.append("- Mismatched links (sample up to 10):")
        for row in mismatches:
            lines.append(
                f"  receipt {row[0]} | {row[1]} | {row[2]} | ${row[3]:,.2f} | receipt_btid={row[4]} vs ledger_btid={row[5]} | status={row[7]}"
            )
    else:
        lines.append("- Mismatched links: none")

    missing = fetch_all(cur, """
        SELECT r.receipt_id, r.vendor_name, r.receipt_date, r.gross_amount,
               r.banking_transaction_id
        FROM receipts r
        WHERE r.banking_transaction_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brml
            WHERE brml.receipt_id = r.receipt_id
              AND brml.banking_transaction_id = r.banking_transaction_id
          )
        ORDER BY r.receipt_date DESC
        LIMIT 10
    """)
    if missing:
        lines.append("- Receipts with banking_transaction_id but no ledger row (sample up to 10):")
        for row in missing:
            lines.append(
                f"  receipt {row[0]} | {row[1]} | {row[2]} | ${row[3]:,.2f} | banking_transaction_id={row[4]}"
            )
    else:
        lines.append("- Missing ledger entries: none")

    # Done
    write_lines(lines)
    for ln in lines:
        print(ln)

    cur.close()
    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

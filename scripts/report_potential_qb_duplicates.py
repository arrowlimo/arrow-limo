import os
import sys
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

"""
Report: Potential QuickBooks-created duplicate receipts

Definition (per Copilot guide rules):
- Group receipts by (receipt_date, gross_amount)
- If the group contains at least one banking-linked receipt
  (banking_transaction_id IS NOT NULL OR created_from_banking = TRUE)
  AND there exist extra receipts with the same (date, amount) that are
  NOT banking-linked AND are NOT cash purchases, then flag the group.

Outputs:
- CSV: reports/potential_qb_duplicates.csv
- Summary printed to stdout

Environment variables (defaults align with Copilot instructions):
- DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
"""

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

OUTPUT_DIR = os.path.join("reports")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "potential_qb_duplicates.csv")


def ensure_output_dir(path: str) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def connect():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fetch_flagged_groups(conn):
    """
    Use SQL aggregation to identify candidate duplicate groups.
    We compute arrays of banking-linked and unlinked-non-cash receipt IDs and vendor names.
    """
    sql = r"""
        SELECT
            r.receipt_date,
            r.gross_amount,
            COUNT(*) AS group_size,
            COUNT(*) FILTER (
                WHERE r.banking_transaction_id IS NOT NULL OR COALESCE(r.created_from_banking, FALSE)
            ) AS banking_linked_count,
            COUNT(*) FILTER (
                WHERE (r.banking_transaction_id IS NULL AND NOT COALESCE(r.created_from_banking, FALSE))
                  AND COALESCE(r.payment_method, '') <> 'cash'
            ) AS unlinked_non_cash_count,
            ARRAY_AGG(r.receipt_id) FILTER (
                WHERE r.banking_transaction_id IS NOT NULL OR COALESCE(r.created_from_banking, FALSE)
            ) AS banking_linked_ids,
            ARRAY_AGG(r.vendor_name) FILTER (
                WHERE r.banking_transaction_id IS NOT NULL OR COALESCE(r.created_from_banking, FALSE)
            ) AS banking_linked_vendors,
                        ARRAY_AGG(r.receipt_id) FILTER (
                WHERE (r.banking_transaction_id IS NULL AND NOT COALESCE(r.created_from_banking, FALSE))
                  AND COALESCE(r.payment_method, '') <> 'cash'
            ) AS unlinked_non_cash_ids,
            ARRAY_AGG(r.vendor_name) FILTER (
                WHERE (r.banking_transaction_id IS NULL AND NOT COALESCE(r.created_from_banking, FALSE))
                  AND COALESCE(r.payment_method, '') <> 'cash'
            ) AS unlinked_non_cash_vendors
        FROM receipts r
        WHERE r.receipt_date IS NOT NULL AND r.gross_amount IS NOT NULL
        GROUP BY r.receipt_date, r.gross_amount
        HAVING COUNT(*) FILTER (
                    WHERE r.banking_transaction_id IS NOT NULL OR COALESCE(r.created_from_banking, FALSE)
               ) >= 1
           AND COUNT(*) FILTER (
                    WHERE (r.banking_transaction_id IS NULL AND NOT COALESCE(r.created_from_banking, FALSE))
                      AND COALESCE(r.payment_method, '') <> 'cash'
               ) >= 1
        ORDER BY r.receipt_date ASC, r.gross_amount ASC
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return cur.fetchall()


def write_csv(rows):
    ensure_output_dir(OUTPUT_DIR)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "receipt_date",
            "gross_amount",
            "group_size",
            "banking_linked_count",
            "unlinked_non_cash_count",
            "banking_linked_ids",
            "banking_linked_vendors",
            "unlinked_non_cash_ids",
            "unlinked_non_cash_vendors",
        ])
        for row in rows:
            # Convert arrays (may be None) to semicolon-joined strings
            def join_list(value):
                if value is None:
                    return ""
                return ";".join(str(v) for v in value)

            writer.writerow([
                row["receipt_date"],
                row["gross_amount"],
                row["group_size"],
                row["banking_linked_count"],
                row["unlinked_non_cash_count"],
                join_list(row.get("banking_linked_ids")),
                join_list(row.get("banking_linked_vendors")),
                join_list(row.get("unlinked_non_cash_ids")),
                join_list(row.get("unlinked_non_cash_vendors")),
            ])


def main():
    try:
        conn = connect()
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

    try:
        rows = fetch_flagged_groups(conn)
    except Exception as e:
        print(f"❌ Query failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(1)

    write_csv(rows)

    flagged_groups = len(rows)
    # Count unlinked non-cash receipts (likely QB-created duplicates)
    duplicate_receipts = 0
    banking_linked_receipts = 0
    total_group_size = 0
    for r in rows:
        total_group_size += int(r.get("group_size") or 0)
        unlinked_ids = r.get("unlinked_non_cash_ids") or []
        banking_ids = r.get("banking_linked_ids") or []
        duplicate_receipts += len(unlinked_ids)
        banking_linked_receipts += len(banking_ids)

    print("✅ Potential QB duplicates report generated")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Flagged groups: {flagged_groups}")
    print(f"Banking-linked receipts in flagged groups: {banking_linked_receipts}")
    print(f"Unlinked non-cash receipts (likely duplicates): {duplicate_receipts}")
    print(f"Total receipts in flagged groups: {total_group_size}")

    try:
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()

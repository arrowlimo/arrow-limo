#!/usr/bin/env python3
"""
Focused invoice-link batch for receipts missing vendor_invoices rows.

Rules (conservative):
- Use queue file ordering (largest amounts first).
- Only create for receipts with:
  gross_amount > 0,
  revenue = 0,
  not excluded,
  not NSF,
  non-blank vendor/canonical vendor,
  and no existing vendor_invoices.source_receipt_id link.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

INVOICE_GAP_CSV = Path(r"L:\limo\data\intake\receipts_missing_invoice_link.csv")
BATCH_LIMIT = 250


def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))



def load_receipt_ids(path: Path) -> list[int]:
    if not path.exists():
        raise FileNotFoundError(f"Missing intake file: {path}")
    ids: list[int] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = (row.get("receipt_id") or "").strip()
            if rid.isdigit():
                ids.append(int(rid))
    return ids



def fetch_invoice_gap_count(cur) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM receipts r
        WHERE NOT EXISTS (
            SELECT 1
            FROM vendor_invoices v
            WHERE v.source_receipt_id = r.receipt_id
        )
        """
    )
    return int(cur.fetchone()["c"])



def main():
    receipt_ids = load_receipt_ids(INVOICE_GAP_CSV)

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        before_gap = fetch_invoice_gap_count(cur)

        created = 0
        created_amount = Decimal("0")
        skipped = 0

        for rid in receipt_ids:
            if created >= BATCH_LIMIT:
                break

            cur.execute(
                """
                SELECT
                    receipt_id,
                    receipt_date,
                    COALESCE(vendor_name,'') AS vendor_name,
                    COALESCE(canonical_vendor,'') AS canonical_vendor,
                    COALESCE(gross_amount,0) AS gross_amount,
                    COALESCE(revenue,0) AS revenue,
                    COALESCE(exclude_from_reports,false) AS exclude_from_reports,
                    COALESCE(is_nsf,false) AS is_nsf
                FROM receipts
                WHERE receipt_id = %s
                """,
                (rid,),
            )
            r = cur.fetchone()
            if not r:
                skipped += 1
                continue

            if to_decimal(r["gross_amount"]) <= Decimal("0"):
                skipped += 1
                continue
            if to_decimal(r["revenue"]) != Decimal("0"):
                skipped += 1
                continue
            if bool(r["exclude_from_reports"]) or bool(r["is_nsf"]):
                skipped += 1
                continue

            vendor = (r["canonical_vendor"] or "").strip() or (r["vendor_name"] or "").strip()
            if not vendor:
                skipped += 1
                continue

            cur.execute(
                """
                INSERT INTO vendor_invoices (
                    vendor_name,
                    invoice_number,
                    invoice_date,
                    invoice_amount,
                    status,
                    notes,
                    source_receipt_id,
                    created_at,
                    updated_at
                )
                SELECT
                    %s,
                    %s,
                    %s,
                    %s,
                    'pending',
                    'Auto-created by invoice-link batch1 from intake queue',
                    %s,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM vendor_invoices v
                    WHERE v.source_receipt_id = %s
                )
                RETURNING vendor_invoice_id
                """,
                (
                    vendor,
                    f"AUTO-RCPT-{r['receipt_id']}",
                    r["receipt_date"],
                    to_decimal(r["gross_amount"]),
                    r["receipt_id"],
                    r["receipt_id"],
                ),
            )
            row = cur.fetchone()
            if row:
                created += 1
                created_amount += to_decimal(r["gross_amount"])
            else:
                skipped += 1

        conn.commit()

        after_gap = fetch_invoice_gap_count(cur)

        print("INVOICE_LINK_BATCH1_DONE")
        print(f"queue_receipt_ids={len(receipt_ids)}")
        print(f"batch_limit={BATCH_LIMIT}")
        print(f"vendor_invoices_created={created}")
        print(f"vendor_invoices_created_amount={created_amount}")
        print(f"skipped={skipped}")
        print(f"before_invoice_gap_count={before_gap}")
        print(f"after_invoice_gap_count={after_gap}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

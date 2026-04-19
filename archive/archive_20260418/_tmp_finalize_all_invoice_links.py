#!/usr/bin/env python3
"""
Finalize invoice-link backlog by creating vendor_invoices for every remaining
receipt missing source_receipt_id linkage.

For review-style rows, status is set to 'review'.
"""

from __future__ import annotations

from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

REVIEW_TERMS = (
    "NSF",
    "REVIEW",
    "UNLINKED",
    "STOP",
    "RETURN",
    "CANCEL",
    "REVERSAL",
)


def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))



def is_review_row(vendor: str, description: str, source: str, is_nsf: bool, excluded: bool) -> bool:
    if is_nsf or excluded:
        return True
    t = f"{vendor} {description}".upper()
    if any(k in t for k in REVIEW_TERMS):
        return True
    s = (source or "").lower()
    return s.startswith("auto_")



def gap_count(cur) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM receipts r
        WHERE NOT EXISTS (
            SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id = r.receipt_id
        )
        """
    )
    return int(cur.fetchone()["c"])



def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        before = gap_count(cur)

        cur.execute(
            """
            SELECT
                r.receipt_id,
                r.receipt_date,
                COALESCE(NULLIF(TRIM(r.canonical_vendor),''), NULLIF(TRIM(r.vendor_name),''), 'UNKNOWN VENDOR') AS vendor,
                COALESCE(r.gross_amount,0) AS gross_amount,
                COALESCE(r.description,'') AS description,
                COALESCE(r.receipt_source,'') AS receipt_source,
                COALESCE(r.is_nsf,false) AS is_nsf,
                COALESCE(r.exclude_from_reports,false) AS exclude_from_reports
            FROM receipts r
            WHERE NOT EXISTS (
                SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id = r.receipt_id
            )
            ORDER BY r.receipt_id
            """
        )

        created = 0
        created_amt = Decimal("0")
        review_created = 0

        for r in cur.fetchall():
            vendor = r["vendor"]
            amount = to_decimal(r["gross_amount"])
            is_review = is_review_row(
                vendor,
                r["description"],
                r["receipt_source"],
                bool(r["is_nsf"]),
                bool(r["exclude_from_reports"]),
            )
            status = "review" if is_review else "pending"
            notes = "Finalized backlog auto-link"
            if is_review:
                notes = "Finalized backlog auto-link; review-class row"

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
                    %s,
                    %s,
                    %s,
                    NOW(),
                    NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id=%s
                )
                RETURNING vendor_invoice_id
                """,
                (
                    vendor[:255],
                    f"FINAL-RCPT-{r['receipt_id']}",
                    r["receipt_date"],
                    amount,
                    status,
                    notes,
                    r["receipt_id"],
                    r["receipt_id"],
                ),
            )
            row = cur.fetchone()
            if row:
                created += 1
                created_amt += amount
                if is_review:
                    review_created += 1

        cur.execute("DELETE FROM vendor_invoices WHERE vendor_name ILIKE '%fibrenew%' AND invoice_number='BANKING_IMPORT'")
        fibrenew_deleted = int(cur.rowcount)

        conn.commit()

        after = gap_count(cur)

        print("FINALIZE_INVOICE_LINKS_DONE")
        print(f"before_gap={before}")
        print(f"after_gap={after}")
        print(f"created={created}")
        print(f"created_amount={created_amt}")
        print(f"review_created={review_created}")
        print(f"fibrenew_banking_import_deleted={fibrenew_deleted}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

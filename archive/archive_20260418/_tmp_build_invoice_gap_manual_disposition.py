#!/usr/bin/env python3
"""
Build manual disposition queue for remaining receipts without invoice link.
"""

from __future__ import annotations

import csv
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

OUT = Path(r"L:\limo\data\intake\manual_invoice_gap_disposition_queue.csv")

REVIEW_TERMS = (
    "NSF",
    "REVIEW",
    "UNLINKED",
    "STOP",
    "RETURN",
    "CANCEL",
    "REVERSAL",
)


def classify(vendor: str, source: str, desc: str) -> tuple[str, str]:
    t = f"{vendor} {desc}".upper()
    src = (source or "").lower()
    if any(k in t for k in REVIEW_TERMS):
        return "review_nonexpense", "placeholder_or_reversal_vendor"
    if src.startswith("auto_"):
        return "review_auto_source", "auto_source"
    return "create_invoice", "normal_expense_vendor"



def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT
            r.receipt_id,
            r.receipt_date,
            COALESCE(NULLIF(TRIM(r.canonical_vendor),''), NULLIF(TRIM(r.vendor_name),''), '') AS vendor,
            COALESCE(r.gross_amount,0) AS gross_amount,
            COALESCE(r.description,'') AS description,
            COALESCE(r.receipt_source,'') AS receipt_source,
            COALESCE(r.gl_account_code,'') AS gl_account_code,
            COALESCE(r.revenue,0) AS revenue,
            COALESCE(r.exclude_from_reports,false) AS exclude_from_reports,
            COALESCE(r.is_nsf,false) AS is_nsf
        FROM receipts r
        WHERE NOT EXISTS (
            SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id = r.receipt_id
        )
        ORDER BY r.gross_amount DESC, r.receipt_date
        """
    )

    rows = []
    for r in cur.fetchall():
        if float(r["gross_amount"] or 0) <= 0:
            continue
        if float(r["revenue"] or 0) != 0:
            continue

        action, reason = classify(r["vendor"], r["receipt_source"], r["description"])
        if bool(r["exclude_from_reports"]) or bool(r["is_nsf"]):
            action, reason = "review_nonexpense", "excluded_or_nsf"

        rows.append([
            r["receipt_id"],
            r["receipt_date"],
            r["vendor"],
            float(r["gross_amount"]),
            r["description"],
            r["receipt_source"],
            r["gl_account_code"],
            action,
            reason,
        ])

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "receipt_id",
            "receipt_date",
            "vendor",
            "gross_amount",
            "description",
            "receipt_source",
            "gl_account_code",
            "recommended_action",
            "reason",
        ])
        w.writerows(rows)

    create_count = sum(1 for x in rows if x[7] == "create_invoice")
    review_count = len(rows) - create_count

    print("INVOICE_GAP_DISPOSITION_QUEUE_DONE")
    print(f"rows={len(rows)}")
    print(f"create_invoice={create_count}")
    print(f"review={review_count}")
    print(f"csv={OUT}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

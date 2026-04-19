#!/usr/bin/env python3
"""
Build curated manual action queues for Batch 3.

Outputs:
- data/intake/manual_missing_receipt_batch3_candidates.csv
- data/intake/manual_invoice_link_batch3_candidates.csv
"""

from __future__ import annotations

import csv
from datetime import datetime
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

OUT_DIR = Path(r"L:\limo\data\intake")
OUT_DIR.mkdir(parents=True, exist_ok=True)

VENDOR_RULES = [
    ("HEFFNER", "HEFFNER", "5150", "LEASE", "high"),
    ("WOODRIDGE", "WOODRIDGE", "5150", "LEASE", "high"),
    ("TELUS", "TELUS", "5750", "TELEPHONE", "high"),
    ("ALL SERVICE INSURANCE", "ALL SERVICE INSURANCE", "5500", "INSURANCE", "high"),
    ("ASI FINANCE", "ASI FINANCE", "5500", "INSURANCE", "high"),
    ("FIRST INSURANCE", "FIRST INSURANCE", "5500", "INSURANCE", "high"),
    ("RIFCO", "RIFCO", "5150", "LEASE", "medium"),
    ("ERLES", "ERLES", "5120", "MAINTENANCE", "high"),
    ("KAL TIRE", "KAL TIRE", "5120", "MAINTENANCE", "high"),
]

EXCLUDE_TEXT = (
    "BANK WITHDRAWAL",
    "ATM WITHDRAWAL",
    "ABM WITHDRAWAL",
    "CASH WITHDRAWAL",
    "INTERAC E-TRANSFER",
    "TRANSFER",
    "PAYMENT RECEIVED",
    "DEPOSIT",
    "INTEREST",
    "NSF",
    "REVERSAL",
    "REFUND",
)

EXCLUDE_VENDOR_FOR_INVOICE_AUTO = (
    "NSF",
    "REVIEW",
    "UNLINKED",
    "STOP",
    "RETURN",
    "CANCEL",
)


def match_vendor_rule(text: str):
    t = (text or "").upper()
    for key, vendor, gl, category, confidence in VENDOR_RULES:
        if key in t:
            return vendor, gl, category, confidence, key
    return "", "", "", "", ""


def is_excluded_text(desc: str) -> bool:
    d = (desc or "").upper()
    return any(x in d for x in EXCLUDE_TEXT)


def is_excluded_invoice_vendor(v: str) -> bool:
    t = (v or "").upper()
    return any(x in t for x in EXCLUDE_VENDOR_FOR_INVOICE_AUTO)


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute(
            """
            SELECT
                bt.transaction_id,
                bt.transaction_date,
                COALESCE(bt.vendor_extracted,'') AS vendor_extracted,
                COALESCE(bt.description,'') AS description,
                COALESCE(bt.category,'') AS category,
                COALESCE(bt.debit_amount,0) AS debit_amount
            FROM banking_transactions bt
            WHERE COALESCE(bt.debit_amount,0) > 0
              AND bt.receipt_id IS NULL
            ORDER BY bt.debit_amount DESC, bt.transaction_date
            """
        )
        bt_rows = cur.fetchall()

        missing_rows = []
        for r in bt_rows:
            desc = r["description"]
            ven = r["vendor_extracted"]
            combined = f"{ven} {desc}".strip()
            vendor, gl, cat, confidence, rule = match_vendor_rule(combined)
            if not rule:
                continue
            if is_excluded_text(desc) and rule not in ("HEFFNER", "WOODRIDGE"):
                continue
            missing_rows.append([
                r["transaction_id"],
                r["transaction_date"],
                ven,
                desc,
                float(r["debit_amount"]),
                r["category"],
                vendor,
                gl,
                cat,
                confidence,
                rule,
            ])

        missing_csv = OUT_DIR / "manual_missing_receipt_batch3_candidates.csv"
        with missing_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "transaction_id",
                "transaction_date",
                "vendor_extracted",
                "description",
                "debit_amount",
                "banking_category",
                "suggested_vendor",
                "suggested_gl",
                "suggested_category",
                "confidence",
                "rule",
            ])
            w.writerows(missing_rows)

        cur.execute(
            """
            SELECT
                r.receipt_id,
                r.receipt_date,
                COALESCE(r.vendor_name,'') AS vendor_name,
                COALESCE(r.canonical_vendor,'') AS canonical_vendor,
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
        invoice_candidates = []
        for r in cur.fetchall():
            vendor = (r["canonical_vendor"] or "").strip() or (r["vendor_name"] or "").strip()
            if not vendor:
                continue
            if float(r["gross_amount"] or 0) <= 0:
                continue
            if float(r["revenue"] or 0) != 0:
                continue
            if bool(r["exclude_from_reports"]) or bool(r["is_nsf"]):
                continue

            confidence = "high"
            reason = "normal_vendor_expense"
            if is_excluded_invoice_vendor(vendor):
                confidence = "manual-review"
                reason = "vendor_placeholder_or_reversal"
            if (r["receipt_source"] or "").lower().startswith("auto_"):
                confidence = "manual-review"
                reason = "auto_source_requires_review"

            invoice_candidates.append([
                r["receipt_id"],
                r["receipt_date"],
                vendor,
                float(r["gross_amount"]),
                r["description"],
                r["receipt_source"],
                r["gl_account_code"],
                confidence,
                reason,
            ])

        invoice_csv = OUT_DIR / "manual_invoice_link_batch3_candidates.csv"
        with invoice_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "receipt_id",
                "receipt_date",
                "vendor",
                "gross_amount",
                "description",
                "receipt_source",
                "gl_account_code",
                "confidence",
                "reason",
            ])
            w.writerows(invoice_candidates)

        ts = datetime.now().isoformat(timespec="seconds")
        print("MANUAL_BATCH3_QUEUES_DONE")
        print(f"generated_at={ts}")
        print(f"missing_receipt_candidates={len(missing_rows)}")
        print(f"invoice_link_candidates={len(invoice_candidates)}")
        print(f"missing_receipt_csv={missing_csv}")
        print(f"invoice_link_csv={invoice_csv}")

        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

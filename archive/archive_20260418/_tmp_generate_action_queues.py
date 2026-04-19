import csv
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
AUDIT_DIR = Path(r"l:\limo\data\audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def export_rows(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1) Auto-tagged cross-account duplicates
    cur.execute(
        """
        SELECT
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.canonical_vendor,
            r.gross_amount,
            r.gst_amount,
            r.gl_account_code,
            r.category,
            r.banking_transaction_id,
            bt.account_number,
            bt.description AS banking_description,
            r.receipt_review_status,
            r.receipt_review_notes,
            r.potential_duplicate
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.receipt_review_status = 'XACC_DUP_AUTO'
        ORDER BY r.receipt_date, r.receipt_id
        """
    )
    auto_rows = cur.fetchall()

    auto_csv = AUDIT_DIR / f"action_queue_1_xacc_dup_auto_{STAMP}.csv"
    export_rows(
        auto_csv,
        [
            "receipt_id", "receipt_date", "vendor_name", "canonical_vendor", "gross_amount", "gst_amount",
            "gl_account_code", "category", "banking_transaction_id", "bank_account", "banking_description",
            "receipt_review_status", "potential_duplicate", "receipt_review_notes"
        ],
        [
            [
                r["receipt_id"], r["receipt_date"], r["vendor_name"], r["canonical_vendor"],
                float(r["gross_amount"] or 0), float(r["gst_amount"] or 0),
                r["gl_account_code"], r["category"], r["banking_transaction_id"], r["account_number"],
                r["banking_description"], r["receipt_review_status"], r["potential_duplicate"], r["receipt_review_notes"]
            ]
            for r in auto_rows
        ],
    )

    # 2) Manual cross-account review queue
    cur.execute(
        """
        SELECT
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.canonical_vendor,
            r.gross_amount,
            r.gst_amount,
            r.gl_account_code,
            r.category,
            r.banking_transaction_id,
            bt.account_number,
            bt.description AS banking_description,
            bt.category AS banking_category,
            r.receipt_review_status,
            r.receipt_review_notes
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.receipt_review_status = 'XACC_REVIEW'
        ORDER BY r.receipt_date, r.receipt_id
        """
    )
    manual_rows = cur.fetchall()

    manual_csv = AUDIT_DIR / f"action_queue_2_xacc_manual_review_{STAMP}.csv"
    export_rows(
        manual_csv,
        [
            "receipt_id", "receipt_date", "vendor_name", "canonical_vendor", "gross_amount", "gst_amount",
            "gl_account_code", "category", "banking_transaction_id", "bank_account", "banking_description", "banking_category",
            "receipt_review_status", "receipt_review_notes"
        ],
        [
            [
                r["receipt_id"], r["receipt_date"], r["vendor_name"], r["canonical_vendor"],
                float(r["gross_amount"] or 0), float(r["gst_amount"] or 0),
                r["gl_account_code"], r["category"], r["banking_transaction_id"], r["account_number"],
                r["banking_description"], r["banking_category"], r["receipt_review_status"], r["receipt_review_notes"]
            ]
            for r in manual_rows
        ],
    )

    # 3) High-confidence mismatch queue
    cur.execute(
        """
        SELECT
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.canonical_vendor,
            r.gross_amount,
            r.gst_amount,
            r.gl_account_code,
            r.category,
            r.banking_transaction_id,
            bt.account_number,
            bt.description AS banking_description,
            bt.category AS banking_category,
            r.receipt_review_status,
            r.receipt_review_notes
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.receipt_review_status = 'REVIEW_MISM_HI'
        ORDER BY r.receipt_date, r.receipt_id
        """
    )
    hi_rows = cur.fetchall()

    hi_csv = AUDIT_DIR / f"action_queue_3_review_mismatch_hi_{STAMP}.csv"
    export_rows(
        hi_csv,
        [
            "receipt_id", "receipt_date", "vendor_name", "canonical_vendor", "gross_amount", "gst_amount",
            "gl_account_code", "category", "banking_transaction_id", "bank_account", "banking_description", "banking_category",
            "receipt_review_status", "receipt_review_notes"
        ],
        [
            [
                r["receipt_id"], r["receipt_date"], r["vendor_name"], r["canonical_vendor"],
                float(r["gross_amount"] or 0), float(r["gst_amount"] or 0),
                r["gl_account_code"], r["category"], r["banking_transaction_id"], r["account_number"],
                r["banking_description"], r["banking_category"], r["receipt_review_status"], r["receipt_review_notes"]
            ]
            for r in hi_rows
        ],
    )

    summary = AUDIT_DIR / f"action_queue_summary_{STAMP}.txt"
    summary.write_text(
        "\n".join([
            "ACTION QUEUE SUMMARY",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            f"Queue 1 - XACC_DUP_AUTO: {len(auto_rows)} rows",
            f"File: {auto_csv}",
            "",
            f"Queue 2 - XACC_REVIEW: {len(manual_rows)} rows",
            f"File: {manual_csv}",
            "",
            f"Queue 3 - REVIEW_MISM_HI: {len(hi_rows)} rows",
            f"File: {hi_csv}",
            "",
            "No data modifications were made by this export.",
        ]),
        encoding="utf-8",
    )

    cur.close()
    conn.close()

    print(f"Q1: {auto_csv}")
    print(f"Q2: {manual_csv}")
    print(f"Q3: {hi_csv}")
    print(f"SUMMARY: {summary}")


if __name__ == "__main__":
    main()

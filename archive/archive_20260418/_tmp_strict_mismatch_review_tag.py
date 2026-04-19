import csv
import re
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
AUDIT_DIR = Path(r"l:\limo\data\audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

STOPWORDS = {
    "THE", "AND", "TO", "OF", "FOR", "PAYMENT", "TRANSACTION", "BANKING", "INTERNET",
    "BRANCH", "DEBIT", "CREDIT", "AUTO", "FROM", "WITH", "PURCHASE", "POS", "POINTOFSALE"
}

KEY_CORR = re.compile(r"(CORRECTION|REVERSAL|REVERSE|STOP\s*PAY(?:MENT)?|NON[- ]?SUFFICIENT|NSF\b|RETURN)", re.I)
KEY_EXPENSE = re.compile(r"(FUEL|GAS|INSURANCE|RESTAURANT|TIRE|REPAIR|LIQUOR|GROCERY|WHOLESALE|HOTEL|TELUS|AMAZON)", re.I)


def tokens(txt: str):
    raw = re.split(r"[^A-Z0-9]+", (txt or "").upper())
    return {t for t in raw if len(t) >= 3 and t not in STOPWORDS}


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT
          r.receipt_id,
          r.receipt_date,
          r.vendor_name,
          r.description AS receipt_description,
          r.gross_amount,
          r.banking_transaction_id,
          r.receipt_review_status,
          r.receipt_review_notes,
          bt.transaction_id,
          bt.transaction_date,
          bt.description AS banking_description,
          bt.category AS banking_category,
          bt.account_number
        FROM receipts r
        JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
        WHERE r.banking_transaction_id IS NOT NULL
        """
    )
    rows = cur.fetchall()

    mismatches = []
    for r in rows:
        receipt_text = f"{r['vendor_name'] or ''} {r['receipt_description'] or ''}".upper()
        banking_text = f"{r['banking_description'] or ''} {r['banking_category'] or ''}".upper()

        rt = tokens(receipt_text)
        bt = tokens(banking_text)

        overlap = len(rt.intersection(bt))
        min_base = max(1, min(len(rt), len(bt)))
        overlap_ratio = overlap / min_base

        r_corr = bool(KEY_CORR.search(receipt_text))
        b_corr = bool(KEY_CORR.search(banking_text))
        r_exp = bool(KEY_EXPENSE.search(receipt_text))
        b_exp = bool(KEY_EXPENSE.search(banking_text))

        reasons = []
        score = 0

        if r_corr != b_corr:
            score += 60
            reasons.append("corr_signal_mismatch")

        if r_exp != b_exp:
            score += 35
            reasons.append("expense_signal_mismatch")

        if overlap_ratio < 0.15:
            score += 30
            reasons.append("low_text_overlap")

        # Skip rows already explicitly handled as NON_EXPENSE_REV
        if (r.get("receipt_review_status") or "") == "NON_EXPENSE_REV":
            continue

        if score >= 60:
            mismatches.append((r, score, "|".join(reasons), overlap_ratio))

    mismatch_ids = sorted({m[0]["receipt_id"] for m in mismatches})

    cur.execute("CREATE TABLE IF NOT EXISTS backup_easyfix_mismatch_review_20260407 AS SELECT * FROM receipts WHERE 1=0")
    if mismatch_ids:
        cur.execute("INSERT INTO backup_easyfix_mismatch_review_20260407 SELECT * FROM receipts WHERE receipt_id = ANY(%s)", (mismatch_ids,))

    # Tag for review only
    if mismatch_ids:
        cur.execute(
            """
            UPDATE receipts
            SET receipt_review_status = COALESCE(NULLIF(receipt_review_status,''), 'REVIEW_MISMATCH'),
                receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                    CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                    'Auto-tagged 2026-04-07 strict pass: receipt text and linked banking text show strong mismatch; manual review required.',
                updated_at = NOW()
            WHERE receipt_id = ANY(%s)
            """,
            (mismatch_ids,),
        )
        updated = cur.rowcount
    else:
        updated = 0

    # Export detail CSV
    csv_path = AUDIT_DIR / f"strict_mismatch_review_queue_{STAMP}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "receipt_id", "receipt_date", "vendor_name", "receipt_description", "gross_amount",
            "banking_transaction_id", "banking_date", "banking_description", "banking_category", "account_number",
            "score", "reasons", "overlap_ratio"
        ])
        for row, score, reasons, overlap_ratio in sorted(mismatches, key=lambda x: (-x[1], x[0]["receipt_date"], x[0]["receipt_id"])):
            w.writerow([
                row["receipt_id"], row["receipt_date"], row["vendor_name"], row["receipt_description"],
                float(row["gross_amount"] or 0),
                row["banking_transaction_id"], row["transaction_date"], row["banking_description"], row["banking_category"], row["account_number"],
                score, reasons, round(overlap_ratio, 4)
            ])

    # Write summary
    cur.execute("SELECT COUNT(*) FROM backup_easyfix_mismatch_review_20260407")
    backup_rows = cur.fetchone()["count"]

    conn.commit()
    cur.close()
    conn.close()

    summary = AUDIT_DIR / f"strict_mismatch_review_summary_{STAMP}.txt"
    summary.write_text(
        "\n".join([
            "STRICT MISMATCH REVIEW SUMMARY",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            f"Rows tagged for review: {updated}",
            f"Backup table rows: {backup_rows}",
            f"Queue CSV: {csv_path}",
            "",
            "No deletion or financial value changes were made.",
        ]),
        encoding="utf-8",
    )

    print(f"UPDATED: {updated}")
    print(f"CSV: {csv_path}")
    print(f"SUMMARY: {summary}")


if __name__ == "__main__":
    main()

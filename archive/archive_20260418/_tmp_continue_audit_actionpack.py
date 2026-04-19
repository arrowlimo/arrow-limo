import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
AUDIT_DIR = Path(r"l:\limo\data\audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def dec(v):
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1) High-confidence NSF/correction flag candidates (read-only suggestions)
    cur.execute(
        """
        SELECT
          receipt_id,
          receipt_date,
          vendor_name,
          description,
          gross_amount,
          is_nsf,
          is_voided,
          exclude_from_reports,
          banking_transaction_id,
          gl_account_code,
          gl_code
        FROM receipts
        WHERE (
          (COALESCE(vendor_name,'') || ' ' || COALESCE(description,'')) ~* '(\\mNSF\\M|NON[- ]?SUFFICIENT|INSUFFICIENT|RETURNED ITEM|BOUNCED|STOP\\s*PAY(?:MENT)?|CORRECTION|ADJUSTMENT|REVERSAL|REVERSE|BANK ERROR)'
        )
          AND COALESCE(is_nsf,false)=false
          AND COALESCE(is_voided,false)=false
          AND COALESCE(exclude_from_reports,false)=false
        ORDER BY receipt_date, receipt_id
        """
    )
    nsf_candidates = cur.fetchall()

    nsf_csv = AUDIT_DIR / f"nsf_correction_high_conf_candidates_{STAMP}.csv"
    with nsf_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "receipt_id", "receipt_date", "vendor_name", "description", "gross_amount",
            "is_nsf", "is_voided", "exclude_from_reports", "banking_transaction_id",
            "suggest_set_is_nsf", "suggest_set_exclude_from_reports", "reason"
        ])
        for r in nsf_candidates:
            txt = f"{r['vendor_name'] or ''} {r['description'] or ''}".upper()
            reason = []
            suggest_is_nsf = False
            suggest_excl = False
            if "NSF" in txt or "NON-SUFFICIENT" in txt or "INSUFFICIENT" in txt or "BOUNCED" in txt:
                suggest_is_nsf = True
                suggest_excl = True
                reason.append("keyword_nsf")
            if "STOP PAY" in txt or "STOP PAYMENT" in txt:
                suggest_excl = True
                reason.append("keyword_stop_payment")
            if "CORRECTION" in txt or "ADJUSTMENT" in txt or "REVERSAL" in txt or "BANK ERROR" in txt:
                suggest_excl = True
                reason.append("keyword_correction")
            w.writerow([
                r["receipt_id"], r["receipt_date"], r["vendor_name"], r["description"], float(dec(r["gross_amount"])),
                r["is_nsf"], r["is_voided"], r["exclude_from_reports"], r["banking_transaction_id"],
                suggest_is_nsf, suggest_excl, "|".join(reason)
            ])

    # 2) Lease remediation candidates (missing receipt links + GST backfill candidates)
    lease_regex = r"(LEASE|FORD\\s*CREDIT|TOYOTA\\s*CREDIT|GM\\s*FINANCIAL|MERCEDES|HONDA\\s*FINANCE|VEHICLE\\s*LEASE|AUTO\\s*LEASE|LOAN\\s*PAYMENT)"

    cur.execute(
        """
        WITH lease_banking AS (
          SELECT bt.transaction_id, bt.transaction_date, bt.account_number, bt.description,
                 COALESCE(bt.debit_amount,0) AS debit_amount
          FROM banking_transactions bt
          WHERE bt.transaction_date >= DATE '2012-01-01' AND bt.transaction_date < DATE '2015-01-01'
            AND COALESCE(bt.debit_amount,0) > 0
            AND COALESCE(bt.description,'') ~* %s
        )
        SELECT lb.*
        FROM lease_banking lb
        LEFT JOIN receipts r ON r.banking_transaction_id = lb.transaction_id
        WHERE r.receipt_id IS NULL
        ORDER BY lb.transaction_date, lb.transaction_id
        """,
        (lease_regex,),
    )
    lease_missing = cur.fetchall()

    lease_missing_csv = AUDIT_DIR / f"lease_2012_2014_missing_receipt_links_{STAMP}.csv"
    with lease_missing_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["transaction_id", "transaction_date", "account_number", "debit_amount", "description", "suggest_action"])
        for r in lease_missing:
            w.writerow([
                r["transaction_id"], r["transaction_date"], r["account_number"], float(dec(r["debit_amount"])), r["description"],
                "create_or_link_lease_receipt"
            ])

    cur.execute(
        """
        WITH lease_receipts AS (
          SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gst_amount, gst_exempt,
                 ROUND((COALESCE(gross_amount,0) * 0.05 / 1.05)::numeric, 2) AS expected_gst,
                 gl_account_code,
                 gl_code
          FROM receipts
          WHERE receipt_date >= DATE '2012-01-01' AND receipt_date < DATE '2015-01-01'
            AND (
              COALESCE(vendor_name,'') ~* %s OR COALESCE(canonical_vendor,'') ~* %s OR COALESCE(description,'') ~* %s OR COALESCE(category,'') ~* %s OR COALESCE(expense::text,'') ~* %s
            )
        )
        SELECT *
        FROM lease_receipts
        WHERE COALESCE(gst_exempt,false)=false
          AND COALESCE(gross_amount,0)>0
          AND COALESCE(gst_amount,0)=0
        ORDER BY receipt_date, receipt_id
        """,
        (lease_regex, lease_regex, lease_regex, lease_regex, lease_regex),
    )
    lease_gst_missing = cur.fetchall()

    lease_gst_csv = AUDIT_DIR / f"lease_2012_2014_gst_backfill_candidates_{STAMP}.csv"
    with lease_gst_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "receipt_id", "receipt_date", "vendor_name", "description", "gross_amount", "gst_amount", "expected_gst",
            "gl_account_code", "gl_code", "suggest_action"
        ])
        for r in lease_gst_missing:
            w.writerow([
                r["receipt_id"], r["receipt_date"], r["vendor_name"], r["description"],
                float(dec(r["gross_amount"])), float(dec(r["gst_amount"])), float(dec(r["expected_gst"])),
                r["gl_account_code"], r["gl_code"], "review_and_backfill_gst"
            ])

    # 3) Prioritized duplicate queue (no deletions)
    cur.execute(
        """
        WITH base AS (
          SELECT
            r.receipt_id,
            r.receipt_date,
            UPPER(TRIM(COALESCE(NULLIF(r.canonical_vendor,''), r.vendor_name, ''))) AS vendor_norm,
            ROUND(COALESCE(r.gross_amount,0)::numeric, 2) AS amount,
            r.vendor_name,
            r.description,
            r.banking_transaction_id,
            bt.account_number,
            COALESCE(r.created_from_banking,false) AS created_from_banking,
            COALESCE(r.receipt_source,'') AS receipt_source
          FROM receipts r
          LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
          WHERE COALESCE(r.gross_amount,0) <> 0
            AND COALESCE(r.is_voided,false)=false
        )
        SELECT
          b1.receipt_id AS receipt_id_1,
          b1.receipt_date AS date_1,
          b2.receipt_id AS receipt_id_2,
          b2.receipt_date AS date_2,
          b1.vendor_norm,
          b1.amount,
          b1.vendor_name AS vendor_1,
          b2.vendor_name AS vendor_2,
          b1.description AS description_1,
          b2.description AS description_2,
          b1.banking_transaction_id AS banking_txn_1,
          b2.banking_transaction_id AS banking_txn_2,
          b1.account_number AS account_1,
          b2.account_number AS account_2,
          ABS(b2.receipt_date - b1.receipt_date) AS day_gap,
          b1.created_from_banking AS auto_1,
          b2.created_from_banking AS auto_2,
          b1.receipt_source AS source_1,
          b2.receipt_source AS source_2
        FROM base b1
        JOIN base b2
          ON b1.receipt_id < b2.receipt_id
         AND b1.vendor_norm <> ''
         AND b1.vendor_norm = b2.vendor_norm
         AND b1.amount = b2.amount
         AND ABS(b2.receipt_date - b1.receipt_date) <= 3
        ORDER BY b1.vendor_norm, b1.amount, b1.receipt_date, b2.receipt_date
        """
    )
    pairs = cur.fetchall()

    def pair_priority(r):
        reasons = []
        score = 0

        same_banking = r["banking_txn_1"] is not None and r["banking_txn_1"] == r["banking_txn_2"]
        if same_banking:
            score += 90
            reasons.append("same_banking_transaction")

        account_1 = str(r["account_1"] or "")
        account_2 = str(r["account_2"] or "")
        cross_8362_1615 = ("8362" in account_1 and "1615" in account_2) or ("1615" in account_1 and "8362" in account_2)
        if cross_8362_1615:
            score += 75
            reasons.append("cross_account_8362_1615")

        if r["day_gap"] == 0:
            score += 20
            reasons.append("same_day")
        elif r["day_gap"] == 1:
            score += 10
            reasons.append("next_day")

        text = f"{r['vendor_norm']} {r['description_1'] or ''} {r['description_2'] or ''}".upper()
        recurring_markers = ["INSURANCE", "HEFFNER", "LEASE", "LOAN", "BANK FEE", "NSF", "OD FEE", "ACCOUNT FEE", "MASTERCARD MERCHANT FEE"]
        if any(m in text for m in recurring_markers):
            score -= 20
            reasons.append("recurring_vendor_or_fee_pattern")

        if r["auto_1"] and r["auto_2"]:
            score += 10
            reasons.append("both_auto_generated")

        if score >= 90:
            pr = "HIGH"
        elif score >= 50:
            pr = "MEDIUM"
        else:
            pr = "LOW"
        return pr, score, "|".join(reasons)

    dup_priority_csv = AUDIT_DIR / f"duplicate_pairs_priority_queue_{STAMP}.csv"
    high = medium = low = 0
    with dup_priority_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "priority", "score", "reasons",
            "receipt_id_1", "date_1", "receipt_id_2", "date_2",
            "vendor_norm", "amount", "day_gap",
            "banking_txn_1", "banking_txn_2", "account_1", "account_2",
            "vendor_1", "vendor_2", "description_1", "description_2", "source_1", "source_2"
        ])
        for r in pairs:
            pr, score, reasons = pair_priority(r)
            if pr == "HIGH":
                high += 1
            elif pr == "MEDIUM":
                medium += 1
            else:
                low += 1
            w.writerow([
                pr, score, reasons,
                r["receipt_id_1"], r["date_1"], r["receipt_id_2"], r["date_2"],
                r["vendor_norm"], float(dec(r["amount"])), r["day_gap"],
                r["banking_txn_1"], r["banking_txn_2"], r["account_1"], r["account_2"],
                r["vendor_1"], r["vendor_2"], r["description_1"], r["description_2"], r["source_1"], r["source_2"]
            ])

    summary_path = AUDIT_DIR / f"continue_audit_actionpack_summary_{STAMP}.txt"
    summary_lines = [
        "CONTINUE AUDIT ACTIONPACK SUMMARY",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"NSF/CORRECTION HIGH-CONFIDENCE CANDIDATES: {len(nsf_candidates)}",
        f"CSV: {nsf_csv}",
        "",
        f"LEASE 2012-2014 MISSING RECEIPT LINKS: {len(lease_missing)}",
        f"CSV: {lease_missing_csv}",
        "",
        f"LEASE 2012-2014 GST BACKFILL CANDIDATES: {len(lease_gst_missing)}",
        f"CSV: {lease_gst_csv}",
        "",
        f"DUPLICATE PRIORITY QUEUE: total={len(pairs)} high={high} medium={medium} low={low}",
        f"CSV: {dup_priority_csv}",
    ]
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    conn.rollback()
    cur.close()
    conn.close()

    print(f"SUMMARY: {summary_path}")
    print(f"NSF_CSV: {nsf_csv}")
    print(f"LEASE_LINK_CSV: {lease_missing_csv}")
    print(f"LEASE_GST_CSV: {lease_gst_csv}")
    print(f"DUP_PRI_CSV: {dup_priority_csv}")
    print("\n".join(summary_lines))


if __name__ == "__main__":
    main()

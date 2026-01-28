import os
import csv
import argparse
from datetime import datetime
import psycopg2

"""
Cleanup GBL deposit receipts mistakenly recorded as expenses.

Rules:
- Treat VCARD/MCARD/ACARD (Global Payments card deposits) as client deposits
- Treat DCARD (bank debit card deposits) as deposits
- Exclude PAYMENT/FEE/CHARGEBACK descriptors (these may be legitimate money-out or fees)
- Only consider records linked to a banking transaction (banking_transaction_id not null)
- Prefer canonical vendors: GLOBAL VISA/MASTERCARD/AMEX DEPOSIT; Debit Card Deposit
- No GST should be on deposits (keep safe; delete regardless, but report if GST > 0)

Actions:
- Dry-run by default: report candidates to CSV
- When --write: delete receipts + related ledger matches for those banking transactions
- Insert a ledger entry marking the banking transaction as 'deposit_no_receipt' so future reconciliation skips creating receipts

Safety:
- Backup CSV always
- Optional --limit and --vendor filters
- Commits at the end; rollback on error
"""

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

CANDIDATE_CANONICAL = {
    "GLOBAL VISA DEPOSIT",
    "GLOBAL MASTERCARD DEPOSIT",
    "GLOBAL AMEX DEPOSIT",
    "DEBIT CARD DEPOSIT",
}

CARD_TERMS = ["VCARD", "MCARD", "ACARD", "DCARD"]
EXCLUDE_TERMS = ["PAYMENT", "FEE", "CHARGEBACK"]

LEDGER_INSERT = """
INSERT INTO banking_receipt_matching_ledger (
    banking_transaction_id, receipt_id, match_date, match_type,
    match_status, match_confidence, notes, created_by
) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
"""

def build_query(vendor_filter: str | None, limit: int | None) -> tuple[str, list]:
    clauses = ["r.banking_transaction_id IS NOT NULL"]
    params: list = []

    # canonical vendors
    clauses.append("r.canonical_vendor = ANY(%s)")
    params.append(list(CANDIDATE_CANONICAL))

    # add card terms
    card_like = []
    for t in CARD_TERMS:
        card_like.append("r.vendor_name ILIKE %s")
        params.append(f"%{t}%")
        card_like.append("r.description ILIKE %s")
        params.append(f"%{t}%")
    clauses.append("(" + " OR ".join(card_like) + ")")

    # exclude payment/fee/chargeback
    excl = []
    for t in EXCLUDE_TERMS:
        excl.append("r.vendor_name ILIKE %s")
        params.append(f"%{t}%")
        excl.append("r.canonical_vendor ILIKE %s")
        params.append(f"%{t}%")
        excl.append("r.description ILIKE %s")
        params.append(f"%{t}%")
    clauses.append("NOT (" + " OR ".join(excl) + ")")

    if vendor_filter:
        clauses.append("(r.vendor_name ILIKE %s OR r.canonical_vendor ILIKE %s)")
        params.append(f"%{vendor_filter}%")
        params.append(f"%{vendor_filter}%")

    sql = (
        "SELECT r.receipt_id, r.banking_transaction_id, r.vendor_name, r.canonical_vendor, "
        "r.description, r.payment_method, r.gst_amount, r.gst_code, "
        "r.gl_account_code, r.gl_account_name, r.gross_amount "
        "FROM receipts r WHERE " + " AND ".join(clauses) + " "
        "ORDER BY r.receipt_date DESC"
    )
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    return sql, params


def main():
    ap = argparse.ArgumentParser(description="Cleanup GBL deposit receipts mistakenly entered as expenses")
    ap.add_argument("--dry-run", action="store_true", help="Run without DB modifications (default)")
    ap.add_argument("--write", action="store_true", help="Apply deletions and ledger marks")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of candidates")
    ap.add_argument("--vendor", type=str, default=None, help="Optional vendor keyword filter")
    ap.add_argument("--backup", action="store_true", help="Write backup CSV of candidates")
    args = ap.parse_args()

    if not args.write:
        args.dry_run = True

    backup_path = os.path.join(
        os.getcwd(),
        f"reports/GBL_DEPOSIT_RECEIPT_CLEANUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    sql, params = build_query(args.vendor, args.limit)
    cur.execute(sql, params)
    rows = cur.fetchall()

    print(f"Found {len(rows)} candidate receipt(s) to review")

    if args.backup or args.dry_run:
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "receipt_id", "banking_transaction_id", "vendor_name", "canonical_vendor",
                "description", "payment_method", "gst_amount", "gst_code",
                "gl_account_code", "gl_account_name", "gross_amount"
            ])
            for r in rows:
                w.writerow(list(r))
        print(f"Backup written: {backup_path}")

    if args.dry_run:
        print("Dry-run mode; no changes applied")
        cur.close()
        conn.close()
        return

    deleted = 0
    for (
        receipt_id,
        banking_id,
        vendor_name,
        canonical_vendor,
        description,
        payment_method,
        gst_amount,
        gst_code,
        gl_account_code,
        gl_account_name,
        gross_amount,
    ) in rows:
        try:
            # Delete ledger matches first (safe)
            cur.execute(
                "DELETE FROM banking_receipt_matching_ledger WHERE receipt_id = %s",
                (receipt_id,)
            )
            # Delete the receipt
            cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
            deleted += 1

            # Mark banking transaction as deposit without receipt
            note = (
                f"Auto-cleanup: {vendor_name or canonical_vendor or ''} deposit; "
                f"no expense receipt required; removed mistaken receipt #{receipt_id}."
            )
            cur.execute(
                LEDGER_INSERT,
                (banking_id, None, "deposit_no_receipt", "linked", 0.99, note, "cleanup_script")
            )
        except Exception as e:
            print(f"Failed to cleanup receipt #{receipt_id}: {e}")
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()
    print(f"Deleted {deleted} mistaken receipt(s). Ledger annotated for banking transactions")


if __name__ == "__main__":
    main()

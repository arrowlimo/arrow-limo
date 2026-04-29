import csv
import json
import os
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB_PASSWORD = os.environ.get("DB_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("Set DB_PASSWORD before running")

OUT_DIR = Path(r"l:\limo\reports\audit_exceptions_2012")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INTERNAL_TRANSFER_CREDIT_KEYWORDS = [
    "DEPOSIT",
    "TRANSFER",
    "E-TRANSFER",
    "ETRANSFER",
    "ELECTRONIC FUNDS TRANSFER",
    "FROM CIBC",
    "INTER ACCOUNT",
    "INTERNAL TRANSFER",
]


def _to_serializable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return str(value)
    return value


def write_csv(path: Path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: _to_serializable(row.get(k)) for k in fieldnames})


def _is_internal_transfer_credit_mismatch(row):
    """Return True for mismatch rows that are credit-side internal transfers."""
    desc = (row.get("banking_description") or "").upper()
    debit = Decimal(str(row.get("debit_amount") or 0))
    credit = Decimal(str(row.get("credit_amount") or 0))
    is_credit_only = debit == Decimal("0") and credit > Decimal("0")
    has_internal_keyword = any(k in desc for k in INTERNAL_TRANSFER_CREDIT_KEYWORDS)
    return is_credit_only and has_internal_keyword


conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password=DB_PASSWORD,
)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='receipts'
    ORDER BY ordinal_position
    """
)
receipt_cols = [r["column_name"] for r in cur.fetchall()]
receipt_colset = set(receipt_cols)

base_receipt_cols = [
    "receipt_id",
    "receipt_date",
    "vendor_name",
    "canonical_vendor",
    "description",
    "gross_amount",
    "payment_method",
    "receipt_source",
    "banking_transaction_id",
    "gl_account_code",
    "gl_code",
    "gst_amount",
    "sales_tax",
    "tax",
    "tax_category",
    "gst_code",
    "gst_exempt",
    "exclude_from_reports",
    "is_split_receipt",
    "split_key",
    "split_group_id",
    "owner_personal_amount",
    "business_personal",
]
selected_receipt_cols = [c for c in base_receipt_cols if c in receipt_colset]

cur.execute(
    f"""
    SELECT {', '.join(selected_receipt_cols)}
    FROM receipts
    WHERE receipt_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
    """
)
receipts_2012 = cur.fetchall()

# 1) Split / multi-link indicators
multi_by_tx = []
if "banking_transaction_id" in receipt_colset:
    cur.execute(
        """
        SELECT banking_transaction_id, COUNT(*) AS receipt_count,
               SUM(COALESCE(gross_amount,0)) AS receipt_sum
        FROM receipts
        WHERE receipt_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
          AND banking_transaction_id IS NOT NULL
        GROUP BY banking_transaction_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, banking_transaction_id
        """
    )
    multi_by_tx = cur.fetchall()

# 2) Amount mismatch between linked receipts and banking debit
linked_amount_mismatch = []
if "banking_transaction_id" in receipt_colset:
    cur.execute(
        """
        WITH r AS (
          SELECT banking_transaction_id,
                 COUNT(*) AS receipt_count,
                 SUM(COALESCE(gross_amount,0))::numeric(14,2) AS receipt_sum
          FROM receipts
          WHERE receipt_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
            AND banking_transaction_id IS NOT NULL
          GROUP BY banking_transaction_id
        )
        SELECT r.banking_transaction_id,
               r.receipt_count,
               r.receipt_sum,
               COALESCE(b.debit_amount,0)::numeric(14,2) AS debit_amount,
             COALESCE(b.credit_amount,0)::numeric(14,2) AS credit_amount,
               COALESCE(b.description,'') AS banking_description,
               b.transaction_date,
               (r.receipt_sum - COALESCE(b.debit_amount,0)::numeric(14,2))::numeric(14,2) AS delta
        FROM r
        JOIN banking_transactions b ON b.transaction_id = r.banking_transaction_id
        WHERE ABS(r.receipt_sum - COALESCE(b.debit_amount,0)::numeric(14,2)) >= 0.01
        ORDER BY ABS(r.receipt_sum - COALESCE(b.debit_amount,0)::numeric(14,2)) DESC
        """
    )
    linked_amount_mismatch = cur.fetchall()

linked_amount_mismatch_excluded_internal_transfer_credit = []
linked_amount_mismatch_actionable = []
for row in linked_amount_mismatch:
    if _is_internal_transfer_credit_mismatch(row):
        linked_amount_mismatch_excluded_internal_transfer_credit.append(row)
    else:
        linked_amount_mismatch_actionable.append(row)

# 3) Unlinked manual/reimbursement receipts
manual_unlinked = []
if "receipt_source" in receipt_colset and "banking_transaction_id" in receipt_colset:
    cur.execute(
        """
        SELECT *
        FROM receipts
        WHERE receipt_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
          AND banking_transaction_id IS NULL
          AND (
                UPPER(COALESCE(receipt_source,'')) LIKE 'MANUAL%%'
             OR UPPER(COALESCE(receipt_source,'')) LIKE 'REIMBURSE%%'
             OR UPPER(COALESCE(receipt_source,'')) = 'CASH'
          )
        ORDER BY receipt_date, receipt_id
        """
    )
    manual_unlinked = cur.fetchall()

# 4) Potential transfer/cash movement still sitting as receipts
transfer_cash_keywords = ["TRANSFER", "E-TRANSFER", "ABM", "ATM", "WITHDRAW", "DEPOSIT", "OWNER DRAW", "OWNER WITHDRAWAL", "PETTY CASH", "INTERAC E-TRANSFER"]
transfer_cash_suspects = []
for r in receipts_2012:
    text = f"{r.get('vendor_name') or ''} {r.get('description') or ''} {r.get('payment_method') or ''}".upper()
    if any(k in text for k in transfer_cash_keywords):
        transfer_cash_suspects.append(r)

# 5) Meal/coffee rows not on GL 6100
meal_keywords = [
    "RESTAURANT", "COFFEE", "TIM HORT", "TIMS", "STARBUCK", "MCDONALD", "A&W", "SUBWAY", "PIZZA", "GRILL", "CAFE", "DINER", "FOOD",
]
meal_needs_review = []
for r in receipts_2012:
    text = f"{r.get('vendor_name') or ''} {r.get('description') or ''}".upper()
    if any(k in text for k in meal_keywords):
        gl = (r.get("gl_account_code") or r.get("gl_code") or "").strip()
        if gl != "6100":
            meal_needs_review.append(r)

# 6) Ice rows with non-zero GST (usually zero)
ice_tax_review = []
if "gst_amount" in receipt_colset:
    for r in receipts_2012:
        text = f"{r.get('vendor_name') or ''} {r.get('description') or ''}".upper()
        if "ICE" in text:
            gst = r.get("gst_amount") or Decimal("0")
            try:
                if Decimal(str(gst)) > Decimal("0"):
                    ice_tax_review.append(r)
            except Exception:
                pass

# 7) May unresolved payment-day checklist (from reconciliation result)
may_unresolved_dates = [
    "2012-05-23",
    "2012-05-24",
    "2012-05-25",
    "2012-05-28",
    "2012-05-30",
    "2012-05-31",
]

pack = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "db": {"host": "localhost", "port": 5432, "dbname": "almsdata", "user": "postgres"},
    "scope": "2012 local-db exception pack",
    "counts": {
        "receipts_2012": len(receipts_2012),
        "multi_receipts_same_banking_tx": len(multi_by_tx),
        "linked_amount_mismatch": len(linked_amount_mismatch),
        "linked_amount_mismatch_actionable": len(linked_amount_mismatch_actionable),
        "linked_amount_mismatch_excluded_internal_transfer_credit": len(
            linked_amount_mismatch_excluded_internal_transfer_credit
        ),
        "manual_or_reimbursement_unlinked": len(manual_unlinked),
        "transfer_cash_suspects": len(transfer_cash_suspects),
        "meal_needs_gl6100_review": len(meal_needs_review),
        "ice_tax_review": len(ice_tax_review),
        "may_unresolved_dates": len(may_unresolved_dates),
    },
    "manual_verification_priority": [
        "linked_amount_mismatch_actionable",
        "multi_receipts_same_banking_tx",
        "manual_or_reimbursement_unlinked",
        "transfer_cash_suspects",
        "meal_needs_gl6100_review",
        "ice_tax_review",
        "may_unresolved_dates",
    ],
    "may_unresolved_dates": may_unresolved_dates,
}

json_path = OUT_DIR / "audit_exceptions_2012_summary.json"
json_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")

write_csv(OUT_DIR / "multi_receipts_same_banking_tx_2012.csv", multi_by_tx)
write_csv(OUT_DIR / "linked_amount_mismatch_2012.csv", linked_amount_mismatch)
write_csv(
    OUT_DIR / "linked_amount_mismatch_actionable_2012.csv",
    linked_amount_mismatch_actionable,
)
write_csv(
    OUT_DIR / "linked_amount_mismatch_excluded_internal_transfer_credit_2012.csv",
    linked_amount_mismatch_excluded_internal_transfer_credit,
)
write_csv(OUT_DIR / "priority_manual_first_2012.csv", linked_amount_mismatch_actionable)
write_csv(OUT_DIR / "manual_or_reimbursement_unlinked_2012.csv", manual_unlinked)
write_csv(OUT_DIR / "transfer_cash_suspects_2012.csv", transfer_cash_suspects)
write_csv(OUT_DIR / "meal_needs_gl6100_review_2012.csv", meal_needs_review)
write_csv(OUT_DIR / "ice_tax_review_2012.csv", ice_tax_review)

print("WROTE", json_path)
print("OUT_DIR", OUT_DIR)
for p in sorted(OUT_DIR.glob("*.csv")):
    print("CSV", p.name)
print("COUNTS", json.dumps(pack["counts"], indent=2))

cur.close()
conn.close()

#!/usr/bin/env python3
"""
Whitelist missing-receipt batch for clearly operational vendors.

Creates receipts only for unlinked banking debits with vendor/description matching
known expense vendors and excludes transfer/ATM/cash withdrawal style rows.
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

MISSING_RECEIPT_CSV = Path(r"L:\limo\data\intake\missing_receipt_intake_queue.csv")
BATCH_LIMIT = 220

WHITELIST_TERMS = (
    "heffner",
    "woodridge",
    "telus",
    "all service insurance",
    "asi finance",
    "rifco",
    "erles",
    "first insurance",
)

EXCLUDE_TERMS = (
    "transfer",
    "e-transfer",
    "withdrawal",
    "atm",
    "abm",
    "cash withdrawal",
    "bank withdrawal",
    "deposit",
    "interest",
    "reversal",
    "refund",
    "nsf",
)



def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))



def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing intake file: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))



def kpi(cur):
    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(debit_amount),0) AS amt FROM banking_transactions WHERE COALESCE(debit_amount,0)>0 AND receipt_id IS NULL")
    r = cur.fetchone()
    return int(r["c"]), to_decimal(r["amt"])



def is_whitelisted(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in WHITELIST_TERMS)



def is_excluded(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in EXCLUDE_TERMS)



def main():
    queue_rows = load_rows(MISSING_RECEIPT_CSV)

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        before_c, before_amt = kpi(cur)

        selected = []
        for row in queue_rows:
            if len(selected) >= BATCH_LIMIT:
                break

            txid_raw = (row.get("transaction_id") or "").strip()
            if not txid_raw.isdigit():
                continue
            txid = int(txid_raw)

            cur.execute(
                """
                SELECT
                    transaction_id,
                    transaction_date,
                    COALESCE(description,'') AS description,
                    COALESCE(vendor_extracted,'') AS vendor_extracted,
                    COALESCE(category,'') AS category,
                    COALESCE(debit_amount,0) AS debit_amount,
                    COALESCE(is_transfer,false) AS is_transfer,
                    COALESCE(is_nsf_charge,false) AS is_nsf_charge,
                    receipt_id
                FROM banking_transactions
                WHERE transaction_id = %s
                """,
                (txid,),
            )
            bt = cur.fetchone()
            if not bt:
                continue
            if bt["receipt_id"] is not None:
                continue
            if bool(bt["is_transfer"]) or bool(bt["is_nsf_charge"]):
                continue
            if to_decimal(bt["debit_amount"]) <= Decimal("0"):
                continue

            combined = f"{bt['vendor_extracted']} {bt['description']}"
            if not is_whitelisted(combined):
                continue
            if is_excluded(bt["description"]) and "heffner" not in combined.lower():
                continue

            cur.execute("SELECT 1 FROM receipts WHERE banking_transaction_id=%s LIMIT 1", (txid,))
            if cur.fetchone() is not None:
                continue

            selected.append(bt)

        created = 0
        created_amt = Decimal("0")
        invoice_created = 0

        for bt in selected:
            vendor = (bt["vendor_extracted"] or "").strip() or "UNKNOWN VENDOR"
            amount = to_decimal(bt["debit_amount"])

            cur.execute(
                """
                INSERT INTO receipts (
                    source_system,
                    source_reference,
                    receipt_date,
                    vendor_name,
                    canonical_vendor,
                    description,
                    currency,
                    gross_amount,
                    gst_amount,
                    net_amount,
                    payment_method,
                    category,
                    revenue,
                    created_from_banking,
                    banking_transaction_id,
                    receipt_source,
                    exclude_from_reports,
                    is_nsf,
                    fiscal_year,
                    created_at,
                    updated_at
                )
                VALUES (
                    'banking_intake_batch2_whitelist',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'CAD',
                    %s,
                    0,
                    %s,
                    'bank_transfer',
                    %s,
                    0,
                    TRUE,
                    %s,
                    'intake_batch2_whitelist',
                    FALSE,
                    FALSE,
                    EXTRACT(YEAR FROM %s::date)::int,
                    NOW(),
                    NOW()
                )
                RETURNING receipt_id
                """,
                (
                    f"BT-{bt['transaction_id']}",
                    bt["transaction_date"],
                    vendor[:255],
                    vendor[:255],
                    (bt["description"] or "")[:4000],
                    amount,
                    amount,
                    (bt["category"] or "")[:255] if bt["category"] else None,
                    bt["transaction_id"],
                    bt["transaction_date"],
                ),
            )
            rid = int(cur.fetchone()["receipt_id"])

            cur.execute("UPDATE banking_transactions SET receipt_id=%s, updated_at=NOW() WHERE transaction_id=%s AND receipt_id IS NULL", (rid, bt["transaction_id"]))

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
                    'Auto-created by missing-receipt whitelist batch2',
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
                    f"WL2-RCPT-{rid}",
                    bt["transaction_date"],
                    amount,
                    rid,
                    rid,
                ),
            )
            if cur.fetchone():
                invoice_created += 1

            created += 1
            created_amt += amount

        cur.execute("DELETE FROM vendor_invoices WHERE vendor_name ILIKE '%fibrenew%' AND invoice_number='BANKING_IMPORT'")
        fibrenew_deleted = int(cur.rowcount)

        conn.commit()

        after_c, after_amt = kpi(cur)

        print("MISSING_RECEIPT_BATCH2_WHITELIST_DONE")
        print(f"queue_rows={len(queue_rows)}")
        print(f"selected={len(selected)}")
        print(f"created_receipts={created}")
        print(f"created_receipts_amount={created_amt}")
        print(f"created_vendor_invoices={invoice_created}")
        print(f"fibrenew_banking_import_deleted={fibrenew_deleted}")
        print(f"before_unlinked={before_c}|{before_amt}")
        print(f"after_unlinked={after_c}|{after_amt}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

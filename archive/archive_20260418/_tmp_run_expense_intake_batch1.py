#!/usr/bin/env python3
"""
Batch 1 expense intake apply script.

Scope:
1) Create receipts for a conservative subset of unlinked banking debits from
   data/intake/missing_receipt_intake_queue.csv.
2) Link those receipts back to banking_transactions.receipt_id.
3) Create vendor_invoices rows for only those newly created receipts.
4) Print before/after metrics.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
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
BATCH_LIMIT = 120

# Conservative exclusion terms for batch-1 auto insert.
EXCLUDE_TERMS = (
    "transfer",
    "e-transfer",
    "interac e-transfer",
    "payment received",
    "deposit",
    "interest",
    "reversal",
    "refund",
    "nsf",
    "service charge",
    "bank fee",
    "monthly fee",
)


@dataclass
class Metrics:
    unlinked_count: int
    unlinked_amount: Decimal
    receipt_count: int
    receipt_amount: Decimal
    invoice_gap_count: int



def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))



def load_csv_candidates(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing intake file: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))



def fetch_metrics(cur) -> Metrics:
    cur.execute(
        """
        SELECT
            COUNT(*) AS c,
            COALESCE(SUM(debit_amount),0) AS amt
        FROM banking_transactions
        WHERE COALESCE(debit_amount,0) > 0
          AND receipt_id IS NULL
        """
    )
    row = cur.fetchone()
    unlinked_count = row["c"]
    unlinked_amount = row["amt"]

    cur.execute(
        """
        SELECT
            COUNT(*) AS c,
            COALESCE(SUM(gross_amount),0) AS amt
        FROM receipts
        """
    )
    row = cur.fetchone()
    receipt_count = row["c"]
    receipt_amount = row["amt"]

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
    invoice_gap_count = cur.fetchone()["c"]

    return Metrics(
        unlinked_count=int(unlinked_count),
        unlinked_amount=to_decimal(unlinked_amount),
        receipt_count=int(receipt_count),
        receipt_amount=to_decimal(receipt_amount),
        invoice_gap_count=int(invoice_gap_count),
    )



def is_excluded_text(text: str) -> bool:
    t = (text or "").lower()
    return any(term in t for term in EXCLUDE_TERMS)



def build_batch_rows(cur, csv_rows: list[dict[str, str]], limit: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in csv_rows:
        if len(out) >= limit:
            break

        tx_id_raw = (row.get("transaction_id") or "").strip()
        if not tx_id_raw.isdigit():
            continue
        tx_id = int(tx_id_raw)

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
            (tx_id,),
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

        desc = str(bt["description"] or "")
        vend = str(bt["vendor_extracted"] or "").strip()
        if len(vend) < 3:
            continue
        if is_excluded_text(desc):
            continue

        cur.execute(
            "SELECT 1 FROM receipts WHERE banking_transaction_id = %s LIMIT 1",
            (tx_id,),
        )
        if cur.fetchone() is not None:
            continue

        out.append(
            {
                "transaction_id": int(bt["transaction_id"]),
                "transaction_date": bt["transaction_date"],
                "description": desc,
                "vendor_extracted": vend,
                "category": str(bt["category"] or ""),
                "debit_amount": to_decimal(bt["debit_amount"]),
            }
        )

    return out



def insert_receipt_for_tx(cur, r: dict[str, object]) -> int:
    tx_date = r["transaction_date"]
    amount = to_decimal(r["debit_amount"])
    vendor = str(r["vendor_extracted"])[:255]
    desc = str(r["description"])[:4000]
    category = str(r["category"])[:255] if r["category"] else None

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
            'banking_intake_batch1',
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
            'intake_batch1_auto',
            FALSE,
            FALSE,
            EXTRACT(YEAR FROM %s::date)::int,
            NOW(),
            NOW()
        )
        RETURNING receipt_id
        """,
        (
            f"BT-{r['transaction_id']}",
            tx_date,
            vendor,
            vendor,
            desc,
            amount,
            amount,
            category,
            int(r["transaction_id"]),
            tx_date,
        ),
    )
    receipt_id = int(cur.fetchone()["receipt_id"])

    cur.execute(
        """
        UPDATE banking_transactions
        SET receipt_id = %s, updated_at = NOW()
        WHERE transaction_id = %s
          AND receipt_id IS NULL
        """,
        (receipt_id, int(r["transaction_id"])),
    )

    return receipt_id



def create_vendor_invoice(cur, receipt_id: int) -> int:
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
            COALESCE(NULLIF(TRIM(r.canonical_vendor),''), NULLIF(TRIM(r.vendor_name),''), 'UNKNOWN VENDOR') AS vendor_name,
            'RCPT-' || r.receipt_id::text AS invoice_number,
            r.receipt_date,
            COALESCE(r.gross_amount,0),
            'pending',
            'Auto-created by intake batch1 from receipt linkage',
            r.receipt_id,
            NOW(),
            NOW()
        FROM receipts r
        WHERE r.receipt_id = %s
          AND NOT EXISTS (
              SELECT 1
              FROM vendor_invoices v
              WHERE v.source_receipt_id = r.receipt_id
          )
        RETURNING vendor_invoice_id
        """,
        (receipt_id,),
    )
    row = cur.fetchone()
    return int(row["vendor_invoice_id"]) if row else 0



def cleanup_fibrenew_banking_import(cur) -> int:
    cur.execute(
        """
        DELETE FROM vendor_invoices
        WHERE vendor_name ILIKE '%fibrenew%'
          AND invoice_number = 'BANKING_IMPORT'
        """
    )
    return int(cur.rowcount)



def main():
    csv_rows = load_csv_candidates(MISSING_RECEIPT_CSV)

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        before = fetch_metrics(cur)
        batch_rows = build_batch_rows(cur, csv_rows, BATCH_LIMIT)

        inserted_receipts: list[int] = []
        for r in batch_rows:
            rid = insert_receipt_for_tx(cur, r)
            inserted_receipts.append(rid)

        invoice_rows = 0
        for rid in inserted_receipts:
            invoice_rows += 1 if create_vendor_invoice(cur, rid) else 0

        fibrenew_deleted = cleanup_fibrenew_banking_import(cur)

        conn.commit()

        after = fetch_metrics(cur)

        inserted_total = sum(
            to_decimal(r["debit_amount"]) for r in batch_rows
        )

        print("BATCH1_APPLY_DONE")
        print(f"csv_rows={len(csv_rows)}")
        print(f"batch_rows_selected={len(batch_rows)}")
        print(f"receipts_inserted={len(inserted_receipts)}")
        print(f"receipts_inserted_total={inserted_total}")
        print(f"vendor_invoices_created={invoice_rows}")
        print(f"fibrenew_banking_import_deleted={fibrenew_deleted}")
        print(
            "before_unlinked_debits="
            f"{before.unlinked_count}|{before.unlinked_amount}"
        )
        print(
            "after_unlinked_debits="
            f"{after.unlinked_count}|{after.unlinked_amount}"
        )
        print(
            "before_receipts="
            f"{before.receipt_count}|{before.receipt_amount}"
        )
        print(
            "after_receipts="
            f"{after.receipt_count}|{after.receipt_amount}"
        )
        print(f"before_invoice_gap_count={before.invoice_gap_count}")
        print(f"after_invoice_gap_count={after.invoice_gap_count}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

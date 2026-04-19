#!/usr/bin/env python3
"""
Apply curated Batch 3 actions from manual queue files.

1) Create receipts for high-confidence missing-receipt candidates.
2) Create vendor_invoices for high-confidence invoice-link candidates.
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

MISSING_CSV = Path(r"L:\limo\data\intake\manual_missing_receipt_batch3_candidates.csv")
INVOICE_CSV = Path(r"L:\limo\data\intake\manual_invoice_link_batch3_candidates.csv")

MAX_MISSING_APPLY = 160
MAX_INVOICE_APPLY = 260


def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))



def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))



def metrics(cur):
    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(debit_amount),0) AS amt FROM banking_transactions WHERE COALESCE(debit_amount,0)>0 AND receipt_id IS NULL")
    x = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS c FROM receipts r WHERE NOT EXISTS (SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id=r.receipt_id)")
    y = cur.fetchone()
    return int(x["c"]), to_decimal(x["amt"]), int(y["c"])



def apply_missing(cur, rows: list[dict[str, str]]):
    created = 0
    created_amt = Decimal("0")
    inv_created = 0

    for row in rows:
        if created >= MAX_MISSING_APPLY:
            break
        if (row.get("confidence") or "").strip().lower() != "high":
            continue

        txid = int(row["transaction_id"])
        cur.execute(
            """
            SELECT
                transaction_id,
                transaction_date,
                COALESCE(description,'') AS description,
                COALESCE(debit_amount,0) AS debit_amount,
                COALESCE(category,'') AS category,
                receipt_id
            FROM banking_transactions
            WHERE transaction_id=%s
            """,
            (txid,),
        )
        bt = cur.fetchone()
        if not bt or bt["receipt_id"] is not None or to_decimal(bt["debit_amount"]) <= 0:
            continue

        vendor = (row.get("suggested_vendor") or "").strip() or (row.get("vendor_extracted") or "").strip() or "UNKNOWN VENDOR"
        gl = (row.get("suggested_gl") or "").strip() or None
        category = (row.get("suggested_category") or "").strip() or (bt["category"] or "") or None
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
                gl_account_code,
                gl_code,
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
                'manual_batch3_apply',
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
                %s,
                %s,
                0,
                TRUE,
                %s,
                'manual_batch3_apply',
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
                bt["description"][:4000],
                amount,
                amount,
                category[:255] if isinstance(category, str) else category,
                gl,
                gl,
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
                'Auto-created from curated manual batch3 missing-receipt apply',
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
                f"MB3-RCPT-{rid}",
                bt["transaction_date"],
                amount,
                rid,
                rid,
            ),
        )
        if cur.fetchone():
            inv_created += 1

        created += 1
        created_amt += amount

    return created, created_amt, inv_created



def apply_invoice(cur, rows: list[dict[str, str]]):
    created = 0
    created_amt = Decimal("0")

    for row in rows:
        if created >= MAX_INVOICE_APPLY:
            break
        if (row.get("confidence") or "").strip().lower() != "high":
            continue

        rid_raw = (row.get("receipt_id") or "").strip()
        if not rid_raw.isdigit():
            continue
        rid = int(rid_raw)

        cur.execute(
            """
            SELECT
                receipt_id,
                receipt_date,
                COALESCE(canonical_vendor,'') AS canonical_vendor,
                COALESCE(vendor_name,'') AS vendor_name,
                COALESCE(gross_amount,0) AS gross_amount
            FROM receipts
            WHERE receipt_id=%s
            """,
            (rid,),
        )
        r = cur.fetchone()
        if not r or to_decimal(r["gross_amount"]) <= 0:
            continue

        vendor = (r["canonical_vendor"] or "").strip() or (r["vendor_name"] or "").strip()
        if not vendor:
            continue

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
                'Auto-created from curated manual batch3 invoice-link apply',
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
                f"MB3I-RCPT-{rid}",
                r["receipt_date"],
                to_decimal(r["gross_amount"]),
                rid,
                rid,
            ),
        )
        if cur.fetchone():
            created += 1
            created_amt += to_decimal(r["gross_amount"])

    return created, created_amt



def main():
    missing_rows = load_csv(MISSING_CSV)
    invoice_rows = load_csv(INVOICE_CSV)

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        b_unlinked_c, b_unlinked_amt, b_invoice_gap = metrics(cur)

        m_created, m_amt, m_inv_created = apply_missing(cur, missing_rows)
        i_created, i_amt = apply_invoice(cur, invoice_rows)

        cur.execute("DELETE FROM vendor_invoices WHERE vendor_name ILIKE '%fibrenew%' AND invoice_number='BANKING_IMPORT'")
        fibrenew_deleted = int(cur.rowcount)

        conn.commit()

        a_unlinked_c, a_unlinked_amt, a_invoice_gap = metrics(cur)

        print("MANUAL_ACTION_BATCH3_APPLY_DONE")
        print(f"missing_queue_rows={len(missing_rows)}")
        print(f"invoice_queue_rows={len(invoice_rows)}")
        print(f"missing_created_receipts={m_created}")
        print(f"missing_created_receipts_amount={m_amt}")
        print(f"missing_created_vendor_invoices={m_inv_created}")
        print(f"invoice_links_created={i_created}")
        print(f"invoice_links_created_amount={i_amt}")
        print(f"fibrenew_banking_import_deleted={fibrenew_deleted}")
        print(f"before_unlinked={b_unlinked_c}|{b_unlinked_amt}")
        print(f"after_unlinked={a_unlinked_c}|{a_unlinked_amt}")
        print(f"before_invoice_gap={b_invoice_gap}")
        print(f"after_invoice_gap={a_invoice_gap}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

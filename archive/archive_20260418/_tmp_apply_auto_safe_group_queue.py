#!/usr/bin/env python3
"""
Apply auto-safe grouped queue into receipts + vendor_invoices.
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

SAFE_CSV = Path(r"L:\limo\data\intake\unlinked_debits_auto_safe_queue.csv")
BATCH_LIMIT = 500

GL_BY_GROUP = {
    "LEASE_FINANCE": ("5150", "LEASE"),
    "INSURANCE": ("5500", "INSURANCE"),
    "TELECOM": ("5750", "TELEPHONE"),
    "DRIVER_PAY_REIMBURSEMENT": ("5260", "DRIVER_PAY_REIMBURSEMENT"),
    "VEHICLE_MAINT": ("5120", "MAINTENANCE"),
    "FUEL": ("5100", "FUEL"),
}


def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def metrics(cur):
    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(debit_amount),0) AS amt FROM banking_transactions WHERE COALESCE(debit_amount,0)>0 AND receipt_id IS NULL")
    x = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS c FROM receipts r WHERE NOT EXISTS (SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id=r.receipt_id)")
    y = cur.fetchone()
    return int(x["c"]), to_decimal(x["amt"]), int(y["c"])


def main():
    if not SAFE_CSV.exists():
        raise SystemExit(f"Missing safe queue: {SAFE_CSV}")

    rows = list(csv.DictReader(open(SAFE_CSV, "r", encoding="utf-8")))

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        b_count, b_amt, b_gap = metrics(cur)

        created = 0
        created_amt = Decimal("0")
        inv_created = 0

        for r in rows:
            if created >= BATCH_LIMIT:
                break

            tid = int(r["transaction_id"])
            grp = r.get("group", "")
            gl, cat = GL_BY_GROUP.get(grp, (None, None))

            cur.execute(
                """
                SELECT transaction_id, transaction_date, COALESCE(description,'') AS description,
                       COALESCE(vendor_extracted,'') AS vendor_extracted,
                       COALESCE(debit_amount,0) AS debit_amount, receipt_id
                FROM banking_transactions
                WHERE transaction_id=%s
                """,
                (tid,),
            )
            bt = cur.fetchone()
            if not bt or bt["receipt_id"] is not None:
                continue
            if to_decimal(bt["debit_amount"]) <= 0:
                continue

            vendor = (bt["vendor_extracted"] or "").strip() or "UNKNOWN VENDOR"
            amount = to_decimal(bt["debit_amount"])

            cur.execute(
                """
                INSERT INTO receipts (
                    source_system, source_reference, receipt_date, vendor_name, canonical_vendor,
                    description, currency, gross_amount, gst_amount, net_amount,
                    payment_method, category, gl_account_code, gl_code,
                    revenue, created_from_banking, banking_transaction_id,
                    receipt_source, exclude_from_reports, is_nsf, fiscal_year,
                    created_at, updated_at
                ) VALUES (
                    'group_auto_apply', %s, %s, %s, %s,
                    %s, 'CAD', %s, 0, %s,
                    'bank_transfer', %s, %s, %s,
                    0, TRUE, %s,
                    'group_auto_apply', FALSE, FALSE, EXTRACT(YEAR FROM %s::date)::int,
                    NOW(), NOW()
                ) RETURNING receipt_id
                """,
                (
                    f"BT-{bt['transaction_id']}",
                    bt["transaction_date"],
                    vendor[:255],
                    vendor[:255],
                    bt["description"][:4000],
                    amount,
                    amount,
                    cat,
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
                    vendor_name, invoice_number, invoice_date, invoice_amount,
                    status, notes, source_receipt_id, created_at, updated_at
                )
                SELECT %s, %s, %s, %s,
                       'pending', 'Auto-created from grouped safe queue', %s, NOW(), NOW()
                WHERE NOT EXISTS (SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id=%s)
                RETURNING vendor_invoice_id
                """,
                (
                    vendor[:255],
                    f"GSAFE-{rid}",
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

        cur.execute("DELETE FROM vendor_invoices WHERE vendor_name ILIKE '%fibrenew%' AND invoice_number='BANKING_IMPORT'")
        fibrenew_deleted = int(cur.rowcount)

        conn.commit()

        a_count, a_amt, a_gap = metrics(cur)

        print("APPLY_SAFE_GROUP_QUEUE_DONE")
        print(f"input_rows={len(rows)}")
        print(f"created_receipts={created}")
        print(f"created_amount={created_amt}")
        print(f"created_vendor_invoices={inv_created}")
        print(f"fibrenew_banking_import_deleted={fibrenew_deleted}")
        print(f"before_unlinked={b_count}|{b_amt}")
        print(f"after_unlinked={a_count}|{a_amt}")
        print(f"before_invoice_gap={b_gap}")
        print(f"after_invoice_gap={a_gap}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

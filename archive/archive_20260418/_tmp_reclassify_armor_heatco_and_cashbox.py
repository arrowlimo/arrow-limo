#!/usr/bin/env python3
"""
Reclassify known cash-box/driver-pay patterns per user rule.

- Jason Rogers / Armor Heatco => driver pay reimbursement bucket
- Cash withdrawal rows already materialized as receipts => cash-box queue review tag
"""

from __future__ import annotations

import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1) Jason Rogers / Armor Heatco => driver pay reimbursement
        cur.execute(
            """
            UPDATE receipts
            SET
                vendor_name = COALESCE(NULLIF(vendor_name,''), 'JASON ROGERS ARMOR HEATCO'),
                canonical_vendor = 'JASON ROGERS ARMOR HEATCO',
                category = 'DRIVER_PAY_REIMBURSEMENT',
                gl_account_code = '5260',
                gl_code = '5260',
                is_driver_reimbursement = TRUE,
                receipt_review_status = 'CASH_BOX_QUEUE',
                receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                    CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                    'Rule 2026-04-08: Jason Rogers/Armor Heatco classified as driver pay reimbursement (cash-box related).',
                updated_at = NOW()
            WHERE created_from_banking = TRUE
              AND (
                    COALESCE(description,'') ILIKE '%armor heatco%'
                 OR COALESCE(description,'') ILIKE '%jason rogers%'
                 OR COALESCE(vendor_name,'') ILIKE '%armor heatco%'
                 OR COALESCE(vendor_name,'') ILIKE '%jason rogers%'
                 OR COALESCE(canonical_vendor,'') ILIKE '%armor heatco%'
                 OR COALESCE(canonical_vendor,'') ILIKE '%jason rogers%'
              )
            """
        )
        armor_rows = int(cur.rowcount)

        # Mark linked vendor invoices for those receipts as review
        cur.execute(
            """
            UPDATE vendor_invoices v
            SET
                status = 'review',
                notes = COALESCE(v.notes,'') ||
                    CASE WHEN COALESCE(v.notes,'')='' THEN '' ELSE E'\n' END ||
                    'Rule 2026-04-08: linked receipt classified as cash-box/driver reimbursement for review.',
                updated_at = NOW()
            WHERE v.source_receipt_id IN (
                SELECT r.receipt_id
                FROM receipts r
                WHERE r.created_from_banking = TRUE
                  AND r.canonical_vendor = 'JASON ROGERS ARMOR HEATCO'
            )
            """
        )
        armor_inv_rows = int(cur.rowcount)

        # 2) Any created receipt with withdrawal language => cash-box queue review tag
        cur.execute(
            """
            UPDATE receipts
            SET
                receipt_review_status = 'CASH_BOX_QUEUE',
                receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                    CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                    'Rule 2026-04-08: withdrawal/cash movement treated as cash-box related queue item.',
                updated_at = NOW()
            WHERE created_from_banking = TRUE
              AND (
                    COALESCE(description,'') ILIKE '%withdrawal%'
                 OR COALESCE(vendor_name,'') ILIKE '%cash withdrawal%'
                 OR COALESCE(canonical_vendor,'') ILIKE '%cash withdrawal%'
              )
            """
        )
        cashbox_receipt_rows = int(cur.rowcount)

        cur.execute(
            """
            UPDATE vendor_invoices v
            SET
                status = 'review',
                notes = COALESCE(v.notes,'') ||
                    CASE WHEN COALESCE(v.notes,'')='' THEN '' ELSE E'\n' END ||
                    'Rule 2026-04-08: withdrawal-linked receipt routed to cash-box queue review.',
                updated_at = NOW()
            WHERE v.source_receipt_id IN (
                SELECT r.receipt_id
                FROM receipts r
                WHERE r.created_from_banking = TRUE
                  AND (
                        COALESCE(r.description,'') ILIKE '%withdrawal%'
                     OR COALESCE(r.vendor_name,'') ILIKE '%cash withdrawal%'
                     OR COALESCE(r.canonical_vendor,'') ILIKE '%cash withdrawal%'
                  )
            )
            """
        )
        cashbox_inv_rows = int(cur.rowcount)

        conn.commit()

        print("RECLASSIFY_RULES_APPLIED")
        print(f"armor_receipts_updated={armor_rows}")
        print(f"armor_vendor_invoices_reviewed={armor_inv_rows}")
        print(f"cashbox_receipts_tagged={cashbox_receipt_rows}")
        print(f"cashbox_vendor_invoices_reviewed={cashbox_inv_rows}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

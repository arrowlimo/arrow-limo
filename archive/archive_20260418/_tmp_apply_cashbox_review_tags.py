#!/usr/bin/env python3
"""
Tag cash-box queue banking transactions for adjudication workflow.
"""

from __future__ import annotations

import csv
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

DECISION_CSV = Path(r"L:\limo\data\intake\cash_box_queue_decision_sheet.csv")


def main():
    if not DECISION_CSV.exists():
        raise SystemExit(f"Missing file: {DECISION_CSV}")

    rows = list(csv.DictReader(open(DECISION_CSV, "r", encoding="utf-8")))
    tx_ids = []
    for r in rows:
        tid = (r.get("transaction_id") or "").strip()
        if tid.isdigit():
            tx_ids.append(int(tid))

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute(
            """
            UPDATE banking_transactions
            SET
                reconciliation_status = 'CASH_BOX_REVIEW',
                reconciliation_notes = COALESCE(reconciliation_notes,'') ||
                    CASE WHEN COALESCE(reconciliation_notes,'')='' THEN '' ELSE E'\n' END ||
                    'Tagged 2026-04-08: cash-box queue adjudication required (reimbursement/business purchase/transfer split).',
                updated_at = NOW()
            WHERE transaction_id = ANY(%s)
            """,
            (tx_ids,)
        )
        updated = int(cur.rowcount)

        conn.commit()

        print("CASHBOX_TAG_APPLY_DONE")
        print(f"decision_rows={len(rows)}")
        print(f"tagged_transactions={updated}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

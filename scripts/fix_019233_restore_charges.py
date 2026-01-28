#!/usr/bin/env python3
"""Restore LMS charge lines for reserve 019233 into almsdata.
- Idempotent: skips if charges already present for reserve_number.
- Inserts five lines matching LMS (Service Fee, Gratuity, GST, Discount, Beverage Order).
"""
import os
import sys
from datetime import datetime
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
RESERVE = "019233"

CHARGES = [
    {"description": "Service Fee", "amount": 1200.00},
    {"description": "Gratuity", "amount": 216.00},
    {"description": "G.S.T.", "amount": 70.25},
    {"description": "Discount", "amount": -60.00},
    {"description": "Beverage Order", "amount": 205.00},
]


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    cur.execute("SELECT charter_id, total_amount_due, paid_amount FROM charters WHERE reserve_number = %s", (RESERVE,))
    row = cur.fetchone()
    if not row:
        print(f"No charter found for reserve {RESERVE}")
        return
    charter_id, total_amount_due, paid_amount = row

    cur.execute("SELECT COUNT(*) FROM charter_charges WHERE reserve_number = %s", (RESERVE,))
    existing = cur.fetchone()[0]
    if existing:
        print(f"Charges already exist for reserve {RESERVE}; skipping insert")
        conn.close()
        return

    now = datetime.utcnow()
    sql = (
        "INSERT INTO charter_charges (reserve_number, charter_id, amount, gst_amount, description, created_at, last_updated_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    params = [
        (RESERVE, charter_id, c["amount"], 0.0, c["description"], now, "manual_restore_019233")
        for c in CHARGES
    ]
    cur.executemany(sql, params)

    # Update charter total to match charges sum if currently zero or mismatched
    charges_sum = sum(c["amount"] for c in CHARGES)
    if total_amount_due is None or abs(float(total_amount_due) - charges_sum) > 0.01:
        cur.execute("UPDATE charters SET total_amount_due = %s WHERE charter_id = %s", (charges_sum, charter_id))

    conn.commit()
    print(f"Inserted {len(CHARGES)} charges for reserve {RESERVE}; total charges {charges_sum:.2f}; paid_amount {float(paid_amount or 0):.2f}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

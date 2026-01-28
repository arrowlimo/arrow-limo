#!/usr/bin/env python3
"""
Link unmatched Square payments to charters by extracting reserve numbers from notes.

- Targets payments with payment_method='credit_card', payment_key present (Square ID), and no charter link yet
- Extracts a 5-6 digit reserve number from `notes`
- Validates existence in `charters`, then updates `payments.charter_id` and `payments.reserve_number`
- Recomputes `charters.paid_amount` and `balance` for the affected reserve

Usage:
  python -X utf8 scripts/link_square_unmatched_via_notes.py         # dry run
  python -X utf8 scripts/link_square_unmatched_via_notes.py --write  # apply changes
  python -X utf8 scripts/link_square_unmatched_via_notes.py --limit 50
"""
import os
import sys
import re
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

RESERVE_REGEX = re.compile(r"\b(\d{5,6})\b")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def extract_reserve(text: str | None) -> str | None:
    if not text:
        return None
    m = RESERVE_REGEX.search(text)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description="Link Square payments to charters via notes reserve number")
    ap.add_argument("--write", action="store_true", help="Apply updates (default is dry-run)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of unmatched payments to process")
    args = ap.parse_args()

    write = args.write

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Pull unmatched Square payments (identified by payment_key and credit_card method)
            cur.execute(
                (
                    """
                    SELECT payment_id, payment_date, amount, payment_key, notes,
                           reserve_number, charter_id
                      FROM payments
                     WHERE payment_method = 'credit_card'
                       AND payment_key IS NOT NULL
                       AND charter_id IS NULL
                     ORDER BY payment_date DESC
                    """
                )
            )
            rows = cur.fetchall()

            if args.limit and len(rows) > args.limit:
                rows = rows[: args.limit]

            if not rows:
                print("✓ No unmatched Square payments found by payment_key/credit_card.")
                return

            print(f"Found {len(rows)} unmatched Square payments to evaluate")
            matched = 0
            applied = 0
            skipped = 0
            for r in rows:
                pid = r["payment_id"]
                amt = float(r["amount"] or 0)
                dt = r["payment_date"]
                notes = r.get("notes") or ""
                existing_res = r.get("reserve_number")

                reserve = extract_reserve(notes)
                if not reserve:
                    print(f"  - {pid}: ${amt:,.2f} on {dt} | no reserve in notes → skip")
                    skipped += 1
                    continue

                # Confirm charter exists
                cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1", (reserve,))
                ch = cur.fetchone()
                if not ch:
                    print(f"  - {pid}: ${amt:,.2f} on {dt} | reserve {reserve} not found → skip")
                    skipped += 1
                    continue

                charter_id = ch["charter_id"]
                matched += 1

                if write:
                    # Update payment link
                    cur.execute(
                        """
                        UPDATE payments
                           SET charter_id = %s,
                               reserve_number = COALESCE(reserve_number, %s),
                               notes = COALESCE(notes, '') || %s,
                               last_updated = NOW()
                         WHERE payment_id = %s
                        """,
                        (
                            charter_id,
                            reserve,
                            f" [AUTO-LINK: Square note reserve {reserve}]",
                            pid,
                        ),
                    )
                    # Recompute charter paid/balance
                    cur.execute(
                        """
                        WITH payment_sum AS (
                             SELECT COALESCE(SUM(amount), 0) AS total_paid
                               FROM payments
                              WHERE reserve_number = %s
                        )
                        UPDATE charters AS c
                           SET paid_amount = ps.total_paid,
                               balance = COALESCE(total_amount_due, 0) - ps.total_paid,
                               updated_at = NOW()
                          FROM payment_sum ps
                         WHERE c.reserve_number = %s
                        """,
                        (reserve, reserve),
                    )
                    applied += 1
                    print(f"  ✓ Linked payment {pid} → reserve {reserve} (charter {charter_id})")
                else:
                    print(f"  • Would link payment {pid} → reserve {reserve} (charter {charter_id})")

            if write:
                conn.commit()
                print(f"\nCOMMIT complete: applied={applied}, matched={matched}, skipped={skipped}")
            else:
                print(f"\nDRY RUN: matched={matched}, skipped={skipped}")


if __name__ == "__main__":
    main()

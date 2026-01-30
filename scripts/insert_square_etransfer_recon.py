#!/usr/bin/env python3
"""
Insert a square_etransfer_reconciliation record by searching banking_transactions
for an Interac e-transfer using name, amount, and optional date window.

Usage example:
  python scripts/insert_square_etransfer_recon.py \
    --name "DRINA DAVIS" \
    --amount 1714.00 \
    --date 2025-06-23 \
    --note "Payment for Thompson wedding July 26 2025"

Optional:
  --charter-id 12345
  --interac-ref CAbeQ6Dk   # if provided, code will derive from this (first 4 upper)
  --days 3                  # date window +/- days (default 3)
"""
import argparse
import os
import re
from datetime import datetime, timedelta

import psycopg2

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REDACTED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432'))
}


essential_like = "(description ILIKE '%E-TRANSFER%' OR description ILIKE '%INTERAC%')"


def derive_code4_from_interac(interac_ref: str | None) -> str | None:
    if not interac_ref:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9]", "", interac_ref)
    if not cleaned:
        return None
    return cleaned[:4].upper()


def derive_code4_from_banking_desc(desc: str | None) -> tuple[str | None, str | None]:
    if not desc:
        return None, None
    m = re.search(r"(\d{12})", desc)
    if not m:
        return None, None
    ref = m.group(1)
    return (ref[-4:], ref)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--amount', type=float, required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--note', default='')
    ap.add_argument('--charter-id', type=int)
    ap.add_argument('--interac-ref')
    ap.add_argument('--days', type=int, default=3)
    args = ap.parse_args()

    tokens = [t.strip() for t in args.name.upper().split() if t.strip()]

    start = (datetime.fromisoformat(args.date) - timedelta(days=args.days)).date()
    end = (datetime.fromisoformat(args.date) + timedelta(days=args.days)).date()

    where = [essential_like, 'credit_amount BETWEEN %s AND %s', 'transaction_date BETWEEN %s AND %s']
    params = [args.amount - 0.01, args.amount + 0.01, start, end]
    for tok in tokens:
        where.append('UPPER(description) LIKE %s')
        params.append(f'%{tok}%')

    sql = f"""
        SELECT transaction_id, transaction_date, description, credit_amount
        FROM banking_transactions
        WHERE {' AND '.join(where)}
        ORDER BY transaction_date DESC
        LIMIT 5
    """

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            if not rows:
                print('No banking_transactions match; nothing inserted.')
                return
            # pick the most recent match
            bt_id, tdate, desc, amt = rows[0]
            code4 = derive_code4_from_interac(args.interac_ref)
            email_ref = args.interac_ref
            if not code4:
                code4, bank_ref = derive_code4_from_banking_desc(desc)
            else:
                _, bank_ref = derive_code4_from_banking_desc(desc)

            cur.execute(
                """
                INSERT INTO square_etransfer_reconciliation(
                    payment_code_4char, square_payment_id, square_payment_key,
                    square_amount, square_date, charter_id,
                    banking_transaction_id, etransfer_reference_number,
                    etransfer_amount, etransfer_date, etransfer_sender_name,
                    interac_email_reference, interac_code_4char,
                    reconciliation_status, reconciliation_method, amount_variance,
                    almsdata_entered_by, almsdata_notes
                )
                VALUES (
                    %s, NULL, NULL,
                    NULL, NULL, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    'pending', 'manual_entry', NULL,
                    %s, %s
                )
                RETURNING reconciliation_id
                """,
                (
                    code4, args.charter_id,
                    bt_id, bank_ref,
                    amt, tdate, args.name,
                    email_ref, code4,
                    os.environ.get('USERNAME') or 'system', args.note
                )
            )
            rid = cur.fetchone()[0]
            conn.commit()
            print(f"Inserted reconciliation_id={rid} code4={code4} bt_id={bt_id} date={tdate} amount={amt}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Link existing office rent receipts to banking transactions by amount/date.

Behavior:
- Finds receipts likely representing office rent (category contains 'rent' and description/vendor has office/lease keywords), with NULL bank_id.
- Matches to banking_transactions where debit_amount equals gross_amount within ±3 days of receipt_date, excluding Woodrow.
- Updates receipts.bank_id and optionally source_reference/source_system where available.

Usage:
  python -X utf8 scripts/match_office_rent_receipts_to_banking.py            # dry-run
  python -X utf8 scripts/match_office_rent_receipts_to_banking.py --write    # apply
"""

import os
import sys
import argparse
from datetime import timedelta

import psycopg2
import psycopg2.extras


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    pwd = os.getenv('DB_PASSWORD', '')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=db, user=user, password=pwd, port=port)


def get_columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply updates (default dry-run)')
    ap.add_argument('--since', default='2017-01-01', help='Only consider receipts on/after this date')
    ap.add_argument('--until', default=None, help='Only consider receipts on/before this date')
    args = ap.parse_args()

    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    rc_cols = get_columns(cur, 'receipts')
    bk_cols = get_columns(cur, 'banking_transactions')

    has_desc = 'description' in rc_cols
    has_vendor = 'vendor_name' in rc_cols
    has_bank_id = 'bank_id' in rc_cols
    has_src_sys = 'source_system' in rc_cols
    has_src_ref = 'source_reference' in rc_cols

    if not has_bank_id:
        print('receipts.bank_id not present; nothing to link.')
        return 0

    # Fetch candidate receipts
    where = ["category ILIKE '%rent%'", 'bank_id IS NULL']
    params = []
    if has_desc:
        where.append("(LOWER(description) ~ ('office|lease|suite|unit|bay') OR description IS NULL)")
    if has_vendor:
        where.append("(LOWER(vendor_name) ~ ('office|lease|suite|unit|bay') OR vendor_name IS NULL)")
        where.append("(vendor_name IS NULL OR vendor_name NOT ILIKE '%WOODROW%')")
    if args.since:
        where.append('receipt_date >= %s')
        params.append(args.since)
    if args.until:
        where.append('receipt_date <= %s')
        params.append(args.until)

    select_cols = [
        'id', 'receipt_date', 'gross_amount',
        'vendor_name' if has_vendor else "'' AS vendor_name",
        'description' if has_desc else "'' AS description",
    ]
    cur.execute(
        f"SELECT {', '.join(select_cols)} FROM receipts WHERE {' AND '.join(where)} ORDER BY receipt_date",
        params,
    )
    receipts = cur.fetchall()
    print(f"Candidate receipts without bank link: {len(receipts)}")

    if not receipts:
        cur.close(); conn.close(); return 0

    # For each, try to match a banking txn by amount/date window
    has_bk_debit = 'debit_amount' in bk_cols
    has_bk_date = 'transaction_date' in bk_cols
    has_bk_desc = 'description' in bk_cols
    has_bk_id = 'transaction_id' in bk_cols
    has_bk_vendor = 'vendor_name' in bk_cols

    updated = 0
    skipped = 0

    for rc in receipts:
        rid = rc['id']
        rdate = rc['receipt_date']
        ramt = float(rc['gross_amount'] or 0)
        rvend = rc['vendor_name'] or ''
        rdesc = rc['description'] or ''

        if ramt <= 0 or rdate is None:
            skipped += 1
            continue

        amt_col = 'debit_amount' if has_bk_debit else 'credit_amount'
        where_b = [f"{amt_col} = %s"]
        params_b = [ramt]
        if has_bk_date:
            where_b.append('transaction_date BETWEEN %s AND %s')
            params_b += [rdate - timedelta(days=3), rdate + timedelta(days=3)]
        if has_bk_desc:
            where_b.append("(description IS NULL OR description NOT ILIKE '%WOODROW%')")

        select_b = [
            'transaction_id' if has_bk_id else 'NULL AS transaction_id',
            'transaction_date' if has_bk_date else 'NULL::date AS transaction_date',
            'COALESCE(vendor_name, \'\')' if has_bk_vendor else "'' AS vendor_name",
            'description' if has_bk_desc else "'' AS description",
            f"{amt_col} AS amount",
        ]

        cur.execute(
            f"SELECT {', '.join(select_b)} FROM banking_transactions WHERE {' AND '.join(where_b)} ORDER BY transaction_date LIMIT 1",
            params_b,
        )
        bt = cur.fetchone()
        if not bt:
            skipped += 1
            continue

        txn_id = bt['transaction_id']
        txn_date = bt['transaction_date']
        bvend = bt['vendor_name']
        bdesc = bt['description']

        # Update link
        updates = ["bank_id = %s"]
        uparams = [txn_id]
        if has_src_sys:
            updates.append("source_system = COALESCE(source_system, 'BANKING')")
        if has_src_ref and txn_id is not None:
            updates.append("source_reference = COALESCE(source_reference, %s)")
            uparams.append(f"OFFICE_RENT_{txn_id}")

        uparams.append(rid)
        sql_u = f"UPDATE receipts SET {', '.join(updates)} WHERE id = %s"

        if args.write:
            cur.execute(sql_u, uparams)
            updated += 1
            print(f"LINKED rc_id={rid} -> bank_id={txn_id} | rc_date={rdate} amt=${ramt:.2f} | bank_date={txn_date} vendor='{bvend}'")
        else:
            print(f"DRY-RUN would link rc_id={rid} -> bank_id={txn_id} | rc_date={rdate} amt=${ramt:.2f} | bank_date={txn_date} vendor='{bvend}'")

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    print(f"Summary: updated={updated}, skipped={skipped}")

    cur.close(); conn.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Interrupted.')
        sys.exit(130)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

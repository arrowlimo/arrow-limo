#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Find and classify occurrences of a specific amount across banking_transactions,
receipts, payments, and email_financial_events. Helps answer questions like
"what are the larger 3079.80" by showing vendors, categories, and linkages.

Usage:
  python -X utf8 scripts/find_amount_details.py --amount 3079.80
  python -X utf8 scripts/find_amount_details.py --amount 3079.80 --since 2017-01-01
"""

import os
import sys
import argparse
from decimal import Decimal, ROUND_HALF_UP

import psycopg2
import psycopg2.extras


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    db = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    pwd = os.getenv('DB_PASSWORD', '')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=db, user=user, password=pwd, port=port)


def d2(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def get_columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--amount', type=float, required=True, help='Amount to search (exact to 2 decimals)')
    ap.add_argument('--since', help='Only consider records on/after date (YYYY-MM-DD)')
    ap.add_argument('--until', help='Only consider records on/before date (YYYY-MM-DD)')
    args = ap.parse_args()

    target = float(d2(args.amount))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    print(f"Searching for amount = {target:.2f}\n")

    # Banking (defensive columns)
    bk_cols = get_columns(cur, 'banking_transactions')
    has_bk_vendor = 'vendor_name' in bk_cols
    has_bk_desc = 'description' in bk_cols
    has_bk_debit = 'debit_amount' in bk_cols
    has_bk_credit = 'credit_amount' in bk_cols
    has_bk_id = 'transaction_id' in bk_cols
    has_bk_date = 'transaction_date' in bk_cols

    bank_where = [
        f"(ROUND(COALESCE({ 'debit_amount' if has_bk_debit else '0' },0),2) = %s OR "
        f" ROUND(COALESCE({ 'credit_amount' if has_bk_credit else '0' },0),2) = %s)"
    ]
    params = [target, target]
    if args.since:
        if has_bk_date:
            bank_where.append('transaction_date >= %s')
        params.append(args.since)
    if args.until:
        if has_bk_date:
            bank_where.append('transaction_date <= %s')
        params.append(args.until)
    sel_bank = [
        'transaction_id' if has_bk_id else 'NULL AS transaction_id',
        'transaction_date' if has_bk_date else 'NULL::date AS transaction_date',
        'vendor_name' if has_bk_vendor else "'' AS vendor_name",
        'description' if has_bk_desc else "'' AS description",
        'debit_amount' if has_bk_debit else '0::numeric AS debit_amount',
        'credit_amount' if has_bk_credit else '0::numeric AS credit_amount',
    ]
    order_bank = 'transaction_date' if has_bk_date else '1'
    cur.execute(
        f"SELECT {', '.join(sel_bank)} FROM banking_transactions WHERE {' AND '.join(bank_where)} ORDER BY {order_bank}",
        params,
    )
    bank_rows = cur.fetchall()
    print(f"Banking matches: {len(bank_rows)}")
    for r in bank_rows[:50]:
        side = 'DEBIT' if float(r['debit_amount'] or 0) > 0 else 'CREDIT'
        amt = r['debit_amount'] if float(r['debit_amount'] or 0) > 0 else r['credit_amount']
        print(f"  {r['transaction_date']} | {side} ${amt:.2f} | id={r['transaction_id']} | vend='{(r['vendor_name'] or '').strip()}' | {((r['description'] or '').strip())[:90]}")
    if len(bank_rows) > 50:
        print(f"  ... and {len(bank_rows)-50} more")

    print()

    # Receipts (defensive columns)
    rc_cols = get_columns(cur, 'receipts')
    has_rc_vendor = 'vendor_name' in rc_cols
    has_rc_cat = 'category' in rc_cols
    has_rc_exp = 'expense_account' in rc_cols
    has_rc_gst = 'gst_amount' in rc_cols
    has_rc_bank = 'bank_id' in rc_cols
    has_rc_srcsys = 'source_system' in rc_cols
    has_rc_srcref = 'source_reference' in rc_cols
    has_rc_desc = 'description' in rc_cols

    rc_where = ["ROUND(gross_amount,2) = %s"]
    params = [target]
    if args.since:
        rc_where.append('receipt_date >= %s')
        params.append(args.since)
    if args.until:
        rc_where.append('receipt_date <= %s')
        params.append(args.until)
    sel_rc = [
        'id', 'receipt_date', 'gross_amount',
        'vendor_name' if has_rc_vendor else "'' AS vendor_name",
        'category' if has_rc_cat else "'' AS category",
        'expense_account' if has_rc_exp else "'' AS expense_account",
        'gst_amount' if has_rc_gst else '0::numeric AS gst_amount',
        'bank_id' if has_rc_bank else 'NULL AS bank_id',
        'source_system' if has_rc_srcsys else "'' AS source_system",
        'source_reference' if has_rc_srcref else "'' AS source_reference",
        'description' if has_rc_desc else "'' AS description",
    ]
    cur.execute(
        f"SELECT {', '.join(sel_rc)} FROM receipts WHERE {' AND '.join(rc_where)} ORDER BY receipt_date",
        params,
    )
    rc_rows = cur.fetchall()
    print(f"Receipt matches: {len(rc_rows)}")
    for r in rc_rows[:50]:
        print(f"  {r['receipt_date']} | rc_id={r['id']} | ${r['gross_amount']:.2f} (GST ${float(r['gst_amount'] or 0):.2f}) | {r['category']} | {r['expense_account'] or ''} | vendor='{r['vendor_name'] or ''}' | bank_id={r['bank_id']} | ref={r['source_reference'] or ''}")
    if len(rc_rows) > 50:
        print(f"  ... and {len(rc_rows)-50} more")

    print()

    # Payments
    pm_where = ["ROUND(COALESCE(amount, payment_amount, 0),2) = %s"]
    params = [target]
    if args.since:
        pm_where.append('payment_date >= %s')
        params.append(args.since)
    if args.until:
        pm_where.append('payment_date <= %s')
        params.append(args.until)
    cur.execute(
        f"""
        SELECT payment_id, payment_date, account_number, reserve_number, amount, payment_amount,
               payment_method, status, notes
        FROM payments
        WHERE {' AND '.join(pm_where)}
        ORDER BY payment_date
        """,
        params,
    )
    pm_rows = cur.fetchall()
    print(f"Payment matches: {len(pm_rows)}")
    for r in pm_rows[:50]:
        amt = r['amount'] if r['amount'] is not None else r['payment_amount']
        print(f"  {r['payment_date']} | pay_id={r['payment_id']} | ${float(amt or 0):.2f} | method={r['payment_method'] or ''} | status={r['status'] or ''} | res={r['reserve_number'] or ''}")
    if len(pm_rows) > 50:
        print(f"  ... and {len(pm_rows)-50} more")

    print()

    # Email financial events
    efe_where = ["ROUND(amount,2) = %s"]
    params = [target]
    if args.since:
        efe_where.append('(email_date::date) >= %s')
        params.append(args.since)
    if args.until:
        efe_where.append('(email_date::date) <= %s')
        params.append(args.until)
    cur.execute(
        f"""
        SELECT id, email_date, subject, entity, status, amount, banking_transaction_id
        FROM email_financial_events
        WHERE {' AND '.join(efe_where)}
        ORDER BY email_date
        """,
        params,
    )
    ef_rows = cur.fetchall()
    print(f"Email event matches: {len(ef_rows)}")
    for r in ef_rows[:50]:
        print(f"  {r['email_date']} | efe_id={r['id']} | ${float(r['amount'] or 0):.2f} | '{(r['entity'] or '')}' | '{(r['subject'] or '')[:70]}' | bank_id={r['banking_transaction_id']}")
    if len(ef_rows) > 50:
        print(f"  ... and {len(ef_rows)-50} more")

    # Quick classification hint
    print("\nHints:")
    if rc_rows:
        cats = { (r['category'] or '').lower() for r in rc_rows }
        print(f"  Receipts categories seen: {', '.join(sorted(c for c in cats if c))}")
    vend = { (r['vendor_name'] or '').strip().lower() for r in bank_rows if (r['vendor_name'] or '').strip() }
    if vend:
        print(f"  Banking vendors seen: {', '.join(sorted(list(vend))[:8])}{' ...' if len(vend)>8 else ''}")

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

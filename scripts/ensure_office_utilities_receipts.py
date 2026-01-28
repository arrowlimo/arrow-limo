#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ensure office utilities payments have receipts linked to banking transactions.

Behavior:
- Scans banking_transactions for likely utilities payments using vendor/keyword patterns.
- Tries email_financial_events as a secondary source to match invoices to banking by amount/date.
- Creates receipts rows for missing ones, linked via bank_id and source_reference.
- Idempotent via deterministic source_hash.
- Calculates GST/HST as INCLUDED in gross using province rate (default AB 5%).

Usage:
  python -X utf8 scripts/ensure_office_utilities_receipts.py --dry-run     # default
  python -X utf8 scripts/ensure_office_utilities_receipts.py --write --since 2017-01-01 --province AB

Notes:
- Uses defensive schema introspection to adapt to column differences across environments.
- Expense account: '6820 - Utilities' when available; category 'Utilities'.
"""

import os
import sys
import argparse
import hashlib
from datetime import date, timedelta

import psycopg2
import psycopg2.extras


TAX_RATES = {
    'AB': 0.05, 'BC': 0.12, 'SK': 0.11, 'MB': 0.12, 'ON': 0.13,
    'QC': 0.14975, 'NB': 0.15, 'NS': 0.15, 'PE': 0.15, 'NL': 0.15,
    'YT': 0.05, 'NT': 0.05, 'NU': 0.05,
}


def calculate_gst_included(gross: float, province: str = 'AB'):
    rate = TAX_RATES.get(province.upper(), 0.05)
    gst = gross * rate / (1.0 + rate)
    net = gross - gst
    return round(gst, 2), round(net, 2)


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


def build_source_hash(*parts):
    m = hashlib.sha256()
    m.update('|'.join(str(p) for p in parts).encode('utf-8'))
    return m.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='2017-01-01', help='Only consider banking txns on/after YYYY-MM-DD')
    ap.add_argument('--until', default=None, help='Only consider banking txns on/before YYYY-MM-DD')
    ap.add_argument('--province', default='AB', help='Province tax rate for GST/HST extraction (default AB)')
    ap.add_argument('--write', action='store_true', help='Apply changes (default dry-run)')
    ap.add_argument('--discover', action='store_true', help='Print candidate utilities transactions/vendors')
    args = ap.parse_args()

    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    receipts_cols = get_columns(cur, 'receipts')
    bank_cols = get_columns(cur, 'banking_transactions')

    has_bank_vendor = 'vendor_name' in bank_cols
    has_bank_desc = 'description' in bank_cols
    has_bank_debit = 'debit_amount' in bank_cols
    has_bank_credit = 'credit_amount' in bank_cols
    has_bank_id = 'transaction_id' in bank_cols
    has_bank_date = 'transaction_date' in bank_cols

    has_receipt_bank_id = 'bank_id' in receipts_cols
    has_created_from_banking = 'created_from_banking' in receipts_cols
    has_source_system = 'source_system' in receipts_cols
    has_source_reference = 'source_reference' in receipts_cols
    has_source_hash = 'source_hash' in receipts_cols
    has_expense_account = 'expense_account' in receipts_cols
    has_business_flag = 'is_business_expense' in receipts_cols or 'business_expense' in receipts_cols

    params = []
    positive = []
    exclusions = []
    if has_bank_desc:
        desc_patterns = [
            '%EPCOR%', '%ENMAX%', '%ATCO%', '%DIRECT ENERGY%', '%POWER%', '%ELECTRIC%', '%ELECTRICITY%', '%HYDRO%',
            '%WATER%', '%SEWER%', '%UTIL%', '%UTILITY%', '%GAS%', '%NATURAL GAS%', '%INTERNET%', '%TELUS%', '%SHAW%', '%ROGERS%', '%BELL%'
        ]
        positive += ["description ILIKE %s"] * len(desc_patterns)
        params += desc_patterns
        exclusions.append("description NOT ILIKE %s")
        params.append('%WOODROW%')
    if has_bank_vendor:
        vend_patterns = [
            '%EPCOR%', '%ENMAX%', '%ATCO%', '%DIRECT ENERGY%', '%CITY%', '%UTIL%', '%UTILITY%', '%TELUS%', '%SHAW%', '%ROGERS%', '%BELL%'
        ]
        positive += ["vendor_name ILIKE %s"] * len(vend_patterns)
        params += vend_patterns

    date_filters = []
    if args.since:
        date_filters.append('transaction_date >= %s')
        params.append(args.since)
    if args.until:
        date_filters.append('transaction_date <= %s')
        params.append(args.until)

    amount_col = 'debit_amount' if has_bank_debit else 'credit_amount'
    where_parts = [f"{amount_col} > 0"]
    if positive:
        where_parts.append(f"( {' OR '.join(positive)} )")
    if exclusions:
        where_parts += exclusions
    if date_filters:
        where_parts += date_filters

    bank_select = [
        'transaction_id' if has_bank_id else 'NULL AS transaction_id',
        'transaction_date' if has_bank_date else 'NULL::date AS transaction_date',
        'COALESCE(vendor_name, \'\')' if has_bank_vendor else "'' AS vendor_name",
        'description' if has_bank_desc else "'' AS description",
        f"{amount_col} AS amount",
    ]
    sql = f"""
        SELECT {', '.join(bank_select)}
        FROM banking_transactions
        WHERE {' AND '.join(where_parts)}
        ORDER BY transaction_date
    """

    cur.execute(sql, params)
    txns = cur.fetchall()

    if args.discover:
        print('Discovery mode: showing up to 25 candidate transactions...')
        for r in txns[:25]:
            print(f"  {r['transaction_date']} | ${float(r['amount'] or 0):8.2f} | vendor='{(r['vendor_name'] or '').strip()}' | desc='{(r['description'] or '').strip()[:80]}'")

    created = 0
    skipped = 0
    print(f"Found {len(txns)} potential utilities payment(s) in banking.")

    for r in txns:
        txn_id = r['transaction_id']
        txn_date = r['transaction_date']
        vendor = (r['vendor_name'] or '').strip()
        desc = (r['description'] or '').strip()
        amount = float(r['amount'] or 0)
        if amount <= 0:
            skipped += 1
            continue

        # Idempotent guards
        exists = False
        if has_receipt_bank_id and txn_id is not None:
            cur.execute('SELECT 1 FROM receipts WHERE bank_id = %s LIMIT 1', (txn_id,))
            if cur.fetchone():
                exists = True

        src_ref = f'OFFICE_UTIL_{txn_id}' if txn_id is not None else None
        if not exists and has_source_reference and src_ref:
            cur.execute('SELECT 1 FROM receipts WHERE source_reference = %s LIMIT 1', (src_ref,))
            if cur.fetchone():
                exists = True

        src_hash = build_source_hash('OFFICE_UTIL', txn_id or 0, txn_date or '', amount)
        if not exists and has_source_hash:
            cur.execute('SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1', (src_hash,))
            if cur.fetchone():
                exists = True

        if exists:
            skipped += 1
            continue

        gst, _net = calculate_gst_included(amount, args.province)

        insert_cols = ['receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'category']
        insert_vals = [txn_date, vendor or 'Utilities', amount, gst, 'Utilities']
        insert_ph = ['%s', '%s', '%s', '%s', '%s']

        if has_receipt_bank_id and txn_id is not None:
            insert_cols.append('bank_id'); insert_vals.append(txn_id); insert_ph.append('%s')
        if has_expense_account:
            insert_cols.append('expense_account'); insert_vals.append('6820 - Utilities'); insert_ph.append('%s')
        if has_created_from_banking:
            insert_cols.append('created_from_banking'); insert_vals.append(True); insert_ph.append('%s')
        if has_source_system:
            insert_cols.append('source_system'); insert_vals.append('BANKING'); insert_ph.append('%s')
        if has_source_reference and src_ref:
            insert_cols.append('source_reference'); insert_vals.append(src_ref); insert_ph.append('%s')
        if has_source_hash:
            insert_cols.append('source_hash'); insert_vals.append(src_hash); insert_ph.append('%s')
        if 'description' in receipts_cols:
            insert_cols.append('description'); insert_vals.append(desc or 'Office utilities payment'); insert_ph.append('%s')
        if has_business_flag:
            if 'is_business_expense' in receipts_cols:
                insert_cols.append('is_business_expense')
            else:
                insert_cols.append('business_expense')
            insert_vals.append(True); insert_ph.append('%s')

        insert_sql = f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({', '.join(insert_ph)})"
        if args.write:
            cur.execute(insert_sql, insert_vals)
            created += 1
            print(f"CREATED utilities receipt {txn_date} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor or 'Utilities'}' | GST ${gst:.2f}")
        else:
            print(f"DRY-RUN would create utilities receipt {txn_date} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor or 'Utilities'}' | GST ${gst:.2f}")

    # Email matching fallback
    try:
        efe_cols = get_columns(cur, 'email_financial_events')
    except Exception:
        efe_cols = []

    if len(txns) == 0 and efe_cols:
        has_subject = 'subject' in efe_cols
        has_entity = 'entity' in efe_cols
        has_status = 'status' in efe_cols
        has_amount = 'amount' in efe_cols
        has_email_date = 'email_date' in efe_cols

        if has_amount and (has_subject or has_entity):
            efe_select = ['id', 'amount', 'email_date' if has_email_date else 'NULL::timestamp AS email_date']
            efe_select.append('subject' if has_subject else "'' AS subject")
            efe_select.append('entity' if has_entity else "'' AS entity")
            if has_status:
                efe_select.append('status')

            efe_where = []
            efe_params = []
            pat = '(epcor|enmax|atco|power|electric|electricity|hydro|water|sewer|util|utility|gas|natural gas|internet|telus|shaw|rogers|bell)'
            if has_subject:
                efe_where.append(f"LOWER(subject) ~ '{pat}'")
            if has_entity:
                efe_where.append(f"LOWER(entity) ~ '{pat}'")
            if args.since and has_email_date:
                efe_where.append('email_date::date >= %s'); efe_params.append(args.since)
            if args.until and has_email_date:
                efe_where.append('email_date::date <= %s'); efe_params.append(args.until)
            if has_status:
                efe_where.append("LOWER(status) IN ('paid','processed','complete')")

            efe_sql = f"SELECT {', '.join(efe_select)} FROM email_financial_events WHERE {' AND '.join(efe_where)} ORDER BY email_date NULLS LAST"
            cur.execute(efe_sql, efe_params)
            events = cur.fetchall()
            print(f"Email scan found {len(events)} potential utilities invoice(s). Attempting banking match by amount/date...")

            for ev in events:
                ev_id = ev['id']; ev_amt = float(ev['amount'] or 0); ev_dt = ev['email_date'].date() if ev['email_date'] else None
                if ev_amt <= 0:
                    continue
                bank_amt_col = 'debit_amount' if has_bank_debit else 'credit_amount'
                bank_date_col = 'transaction_date' if has_bank_date else None
                bank_where = [f"{bank_amt_col} = %s"]; bank_params = [ev_amt]
                if bank_date_col and ev_dt:
                    bank_where.append(f"{bank_date_col} BETWEEN %s AND %s"); bank_params += [ev_dt - timedelta(days=3), ev_dt + timedelta(days=3)]
                if has_bank_desc:
                    bank_where.append("description NOT ILIKE '%WOODROW%'")
                bank_sel = [
                    'transaction_id' if has_bank_id else 'NULL AS transaction_id',
                    'transaction_date' if has_bank_date else 'NULL::date AS transaction_date',
                    'COALESCE(vendor_name, \'\')' if has_bank_vendor else "'' AS vendor_name",
                    'description' if has_bank_desc else "'' AS description",
                    f"{bank_amt_col} AS amount",
                ]
                bank_sql = f"SELECT {', '.join(bank_sel)} FROM banking_transactions WHERE {' AND '.join(bank_where)} ORDER BY transaction_date LIMIT 1"
                cur.execute(bank_sql, bank_params)
                b = cur.fetchone()
                if not b:
                    continue

                txn_id = b['transaction_id']; txn_date = b['transaction_date']
                vendor = (b['vendor_name'] or ev.get('entity') or 'Utilities').strip()
                desc = (b['description'] or ev.get('subject') or 'Utilities payment').strip()
                amount = float(b['amount'] or 0)

                exists = False
                if has_receipt_bank_id and txn_id is not None:
                    cur.execute('SELECT 1 FROM receipts WHERE bank_id = %s LIMIT 1', (txn_id,))
                    if cur.fetchone():
                        exists = True
                src_ref = f'OFFICE_UTIL_{txn_id}' if txn_id is not None else f'OFFICE_UTIL_EMAIL_{ev_id}'
                if not exists and has_source_reference and src_ref:
                    cur.execute('SELECT 1 FROM receipts WHERE source_reference = %s LIMIT 1', (src_ref,))
                    if cur.fetchone():
                        exists = True
                src_hash = build_source_hash('OFFICE_UTIL', txn_id or 0, txn_date or '', amount, ev_id)
                if not exists and has_source_hash:
                    cur.execute('SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1', (src_hash,))
                    if cur.fetchone():
                        exists = True
                if exists:
                    skipped += 1
                    continue

                gst, _ = calculate_gst_included(amount, args.province)

                insert_cols = ['receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'category']
                insert_vals = [txn_date or (ev_dt or date.today()), vendor, amount, gst, 'Utilities']
                insert_ph = ['%s', '%s', '%s', '%s', '%s']
                if has_receipt_bank_id and txn_id is not None:
                    insert_cols.append('bank_id'); insert_vals.append(txn_id); insert_ph.append('%s')
                if has_expense_account:
                    insert_cols.append('expense_account'); insert_vals.append('6820 - Utilities'); insert_ph.append('%s')
                if has_created_from_banking:
                    insert_cols.append('created_from_banking'); insert_vals.append(True); insert_ph.append('%s')
                if has_source_system:
                    insert_cols.append('source_system'); insert_vals.append('EMAIL+BANKING'); insert_ph.append('%s')
                if has_source_reference and src_ref:
                    insert_cols.append('source_reference'); insert_vals.append(src_ref); insert_ph.append('%s')
                if has_source_hash:
                    insert_cols.append('source_hash'); insert_vals.append(src_hash); insert_ph.append('%s')
                if 'description' in receipts_cols:
                    insert_cols.append('description'); insert_vals.append(desc); insert_ph.append('%s')
                if has_business_flag:
                    if 'is_business_expense' in receipts_cols:
                        insert_cols.append('is_business_expense')
                    else:
                        insert_cols.append('business_expense')
                    insert_vals.append(True); insert_ph.append('%s')

                insert_sql = f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({', '.join(insert_ph)})"
                if args.write:
                    cur.execute(insert_sql, insert_vals)
                    created += 1
                    print(f"CREATED (email-matched) utilities receipt {txn_date or ev_dt} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor}' | GST ${gst:.2f}")
                else:
                    print(f"DRY-RUN would create (email-matched) utilities receipt {txn_date or ev_dt} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor}' | GST ${gst:.2f}")

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    print(f"Summary: created={created}, skipped_existing={skipped}")
    cur.close(); conn.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted.'); sys.exit(130)
    except Exception as e:
        print(f'Error: {e}'); sys.exit(1)

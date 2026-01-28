#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ensure office rent payments have receipts linked to banking transactions.

Behavior:
- Scans banking_transactions for likely office rent payments using keyword patterns.
- Skips known shop/parking rent to Woodrow to avoid duplicates.
- Creates receipts rows for missing ones, linked via bank_id and source_reference.
- Idempotent via deterministic source_hash.

Usage:
  python -X utf8 scripts/ensure_office_rent_receipts.py --dry-run     # default
  python -X utf8 scripts/ensure_office_rent_receipts.py --write --since 2017-01-01

Notes:
- Uses defensive schema introspection to adapt to column differences across environments.
- Default GST is 0.00 (unknown landlord GST registration). Adjust later if invoices confirm GST.
"""

import os
import sys
import argparse
import hashlib
from datetime import datetime, date

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


def build_source_hash(*parts):
    m = hashlib.sha256()
    m.update('|'.join(str(p) for p in parts).encode('utf-8'))
    return m.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', help='Only consider banking txns on/after this YYYY-MM-DD', default='2017-01-01')
    ap.add_argument('--until', help='Only consider banking txns on/before this YYYY-MM-DD', default=None)
    ap.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    ap.add_argument('--discover', action='store_true', help='Print candidate office rent transactions/vendors for review')
    args = ap.parse_args()

    since = args.since
    until = args.until

    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Introspect schemas
    receipts_cols = get_columns(cur, 'receipts')
    bank_cols = get_columns(cur, 'banking_transactions')

    # Column availability flags
    has_bank_vendor = 'vendor_name' in bank_cols
    has_bank_desc = 'description' in bank_cols
    has_bank_debit = 'debit_amount' in bank_cols
    has_bank_credit = 'credit_amount' in bank_cols
    has_bank_id = 'transaction_id' in bank_cols
    has_bank_date = 'transaction_date' in bank_cols

    # Receipts columns (defensive)
    has_receipt_bank_id = 'bank_id' in receipts_cols
    has_created_from_banking = 'created_from_banking' in receipts_cols
    has_source_system = 'source_system' in receipts_cols
    has_source_reference = 'source_reference' in receipts_cols
    has_source_hash = 'source_hash' in receipts_cols
    has_expense_account = 'expense_account' in receipts_cols
    has_business_flag = 'is_business_expense' in receipts_cols or 'business_expense' in receipts_cols

    # Build banking filter: exclude Woodrow (shop/parking), include office/lease keywords and Fibrenew
    params = []
    positive_clauses = []
    exclusion_clauses = []
    if has_bank_desc:
        # Focused patterns to avoid GSUITE/office-supplies false positives
        desc_patterns = ['%OFFICE RENT%', '%OFFICE LEASE%', '%LEASE PAYMENT%', '%RENT%', '%LEASE%', '%FIBRENEW%']
        positive_clauses += ["description ILIKE %s"] * len(desc_patterns)
        params += desc_patterns
        # Exclusions (avoid Woodrow shop rent; avoid GSuite; avoid office supplies store)
        exclusion_clauses.append("description NOT ILIKE %s"); params.append('%WOODROW%')
        exclusion_clauses.append("description NOT ILIKE %s"); params.append('%GSUITE%')
        exclusion_clauses.append("description NOT ILIKE %s"); params.append('%PRAIRIE OFFICE%')
    if has_bank_vendor:
        vend_patterns = ['%LEASE%', '%RENT%', '%FIBRENEW%']
        positive_clauses += ["vendor_name ILIKE %s"] * len(vend_patterns)
        params += vend_patterns

    date_filters = []
    if since:
        date_filters.append("transaction_date >= %s")
        params.append(since)
    if until:
        date_filters.append("transaction_date <= %s")
        params.append(until)

    # Choose amount side: outflows are typically in debit_amount
    amount_filter = f"{('debit_amount' if has_bank_debit else 'credit_amount')} > 0"

    where_parts = [amount_filter]
    if positive_clauses:
        where_parts.append(f"( {' OR '.join(positive_clauses)} )")
    if exclusion_clauses:
        where_parts += exclusion_clauses
    if date_filters:
        where_parts += date_filters

    bank_select_cols = [
        'transaction_id' if has_bank_id else 'NULL AS transaction_id',
        'transaction_date' if has_bank_date else 'NULL::date AS transaction_date',
        'COALESCE(vendor_name, \'\')' if has_bank_vendor else '\'\' AS vendor_name',
        'description' if has_bank_desc else '\'\' AS description',
        ('debit_amount' if has_bank_debit else 'credit_amount') + ' AS amount',
    ]

    sql = f"""
        SELECT {', '.join(bank_select_cols)}
        FROM banking_transactions
        WHERE {' AND '.join(where_parts)}
        ORDER BY transaction_date
    """

    cur.execute(sql, params)
    txns = cur.fetchall()

    if args.discover:
        # Print a quick summary of candidate vendors/phrases and amounts
        print("Discovery mode: showing up to 25 candidate transactions...")
        shown = 0
        for row in txns[:25]:
            print(f"  {row['transaction_date']} | ${float(row['amount'] or 0):8.2f} | vendor='{(row['vendor_name'] or '').strip()}' | desc='{(row['description'] or '').strip()[:80]}'")
            shown += 1
        if shown == 0:
            print("  No candidates matched with current patterns.")

    created = 0
    skipped = 0

    print(f"Found {len(txns)} potential office rent payment(s) in banking.")

    for row in txns:
        txn_id = row['transaction_id']
        txn_date = row['transaction_date']
        vendor = (row['vendor_name'] or '').strip()
        desc = (row['description'] or '').strip()
        amount = float(row['amount'] or 0)

        if amount <= 0:
            skipped += 1
            continue

        # Idempotent guards: existing receipt by bank_id or source_reference/hash
        receipt_exists = False
        if has_receipt_bank_id and txn_id is not None:
            cur.execute("SELECT 1 FROM receipts WHERE bank_id = %s LIMIT 1", (txn_id,))
            if cur.fetchone():
                receipt_exists = True

        src_ref = f"OFFICE_RENT_{txn_id}" if txn_id is not None else None
        if not receipt_exists and has_source_reference and src_ref:
            cur.execute("SELECT 1 FROM receipts WHERE source_reference = %s LIMIT 1", (src_ref,))
            if cur.fetchone():
                receipt_exists = True

        src_hash = build_source_hash('OFFICE_RENT', txn_id or 0, txn_date or '', amount)
        if not receipt_exists and has_source_hash:
            cur.execute("SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1", (src_hash,))
            if cur.fetchone():
                receipt_exists = True

        if receipt_exists:
            skipped += 1
            continue

        # Prepare insert using defensive column set
        insert_cols = ['receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'category']
        insert_vals = [txn_date, vendor or 'Office Rent', amount, 0.00, 'Rent']
        insert_ph = ['%s', '%s', '%s', '%s', '%s']

        if has_receipt_bank_id and txn_id is not None:
            insert_cols.append('bank_id')
            insert_vals.append(txn_id)
            insert_ph.append('%s')

        if has_expense_account:
            insert_cols.append('expense_account')
            insert_vals.append('6800 - Rent')
            insert_ph.append('%s')

        if has_created_from_banking:
            insert_cols.append('created_from_banking')
            insert_vals.append(True)
            insert_ph.append('%s')

        if has_source_system:
            insert_cols.append('source_system')
            insert_vals.append('BANKING')
            insert_ph.append('%s')

        if has_source_reference and src_ref:
            insert_cols.append('source_reference')
            insert_vals.append(src_ref)
            insert_ph.append('%s')

        if has_source_hash:
            insert_cols.append('source_hash')
            insert_vals.append(src_hash)
            insert_ph.append('%s')

        if 'description' in receipts_cols:
            insert_cols.append('description')
            insert_vals.append((desc or 'Office rent payment'))
            insert_ph.append('%s')

        if has_business_flag:
            # Use whichever column exists
            if 'is_business_expense' in receipts_cols:
                insert_cols.append('is_business_expense')
            else:
                insert_cols.append('business_expense')
            insert_vals.append(True)
            insert_ph.append('%s')

        insert_sql = f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({', '.join(insert_ph)})"

        if args.write:
            cur.execute(insert_sql, insert_vals)
            created += 1
            print(f"CREATED receipt for {txn_date} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor or 'Office Rent'}'")
        else:
            print(f"DRY-RUN would create receipt for {txn_date} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor or 'Office Rent'}'")

    # If none found in banking by keyword, try using email_financial_events to locate paid office rent invoices
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
        has_banking_fk = 'banking_transaction_id' in efe_cols

        if has_amount and (has_subject or has_entity):
            efe_select = [
                'id',
                'amount',
                'email_date' if has_email_date else 'NULL::timestamp AS email_date',
            ]
            if has_subject:
                efe_select.append('subject')
            else:
                efe_select.append("'' AS subject")
            if has_entity:
                efe_select.append('entity')
            else:
                efe_select.append("'' AS entity")
            if has_status:
                efe_select.append('status')
            else:
                efe_select.append("'' AS status")

            efe_where = []
            efe_params = []
            # Keyword filters
            if has_subject:
                efe_where.append("(LOWER(subject) ~ ('office|rent|lease|suite|unit|bay'))")
            if has_entity:
                efe_where.append("(LOWER(entity) ~ ('office|rent|lease|suite|unit|bay'))")
            if since and has_email_date:
                efe_where.append('email_date::date >= %s')
                efe_params.append(since)
            if until and has_email_date:
                efe_where.append('email_date::date <= %s')
                efe_params.append(until)
            if has_status:
                efe_where.append("LOWER(status) IN ('paid','processed','complete')")

            efe_sql = f"""
                SELECT {', '.join(efe_select)}
                FROM email_financial_events
                WHERE {' AND '.join(efe_where)}
                ORDER BY email_date NULLS LAST
            """

            cur.execute(efe_sql, efe_params)
            events = cur.fetchall()
            print(f"Email scan found {len(events)} potential office rent invoice(s). Attempting banking match by amount/date...")

            for ev in events:
                ev_id = ev['id']
                ev_amt = float(ev['amount'] or 0)
                ev_dt = ev['email_date'].date() if ev['email_date'] else None
                ev_subject = ev['subject'] or ''
                ev_entity = ev['entity'] or ''

                if ev_amt <= 0:
                    continue

                # Search banking by amount and date proximity (±3 days) for outflow side
                bank_amt_col = 'debit_amount' if has_bank_debit else 'credit_amount'
                bank_date_col = 'transaction_date' if has_bank_date else None

                bank_where = [f"{bank_amt_col} = %s"]
                bank_params = [ev_amt]
                if bank_date_col and ev_dt:
                    bank_where.append(f"{bank_date_col} BETWEEN %s AND %s")
                    bank_params += [ev_dt.replace(day=ev_dt.day), ev_dt]
                    # A simple window: ev_dt-3 to ev_dt+3
                    from datetime import timedelta
                    bank_params[-2] = ev_dt - timedelta(days=3)
                    bank_params[-1] = ev_dt + timedelta(days=3)

                bank_where.append("(description NOT ILIKE '%WOODROW%')") if has_bank_desc else None

                bank_sel = [
                    'transaction_id' if has_bank_id else 'NULL AS transaction_id',
                    'transaction_date' if has_bank_date else 'NULL::date AS transaction_date',
                    'COALESCE(vendor_name, \'\')' if has_bank_vendor else "'' AS vendor_name",
                    'description' if has_bank_desc else "'' AS description",
                    f"{bank_amt_col} AS amount",
                ]

                bank_sql = f"SELECT {', '.join(bank_sel)} FROM banking_transactions WHERE {' AND '.join(bank_where)} ORDER BY transaction_date LIMIT 1"
                cur.execute(bank_sql, bank_params)
                bmatch = cur.fetchone()
                if not bmatch:
                    continue

                txn_id = bmatch['transaction_id']
                txn_date = bmatch['transaction_date']
                vendor = (bmatch['vendor_name'] or ev_entity or 'Office Rent').strip()
                desc = (bmatch['description'] or ev_subject or 'Office rent payment').strip()
                amount = float(bmatch['amount'] or 0)

                # Idempotent guards again
                receipt_exists = False
                if has_receipt_bank_id and txn_id is not None:
                    cur.execute("SELECT 1 FROM receipts WHERE bank_id = %s LIMIT 1", (txn_id,))
                    if cur.fetchone():
                        receipt_exists = True

                src_ref = f"OFFICE_RENT_{txn_id}" if txn_id is not None else f"OFFICE_RENT_EMAIL_{ev_id}"
                if not receipt_exists and has_source_reference and src_ref:
                    cur.execute("SELECT 1 FROM receipts WHERE source_reference = %s LIMIT 1", (src_ref,))
                    if cur.fetchone():
                        receipt_exists = True

                src_hash = build_source_hash('OFFICE_RENT', txn_id or 0, txn_date or '', amount, ev_id)
                if not receipt_exists and has_source_hash:
                    cur.execute("SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1", (src_hash,))
                    if cur.fetchone():
                        receipt_exists = True

                if receipt_exists:
                    skipped += 1
                    continue

                insert_cols = ['receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'category']
                insert_vals = [txn_date or (ev_dt or date.today()), vendor, amount, 0.00, 'Rent']
                insert_ph = ['%s', '%s', '%s', '%s', '%s']

                if has_receipt_bank_id and txn_id is not None:
                    insert_cols.append('bank_id')
                    insert_vals.append(txn_id)
                    insert_ph.append('%s')

                if has_expense_account:
                    insert_cols.append('expense_account')
                    insert_vals.append('6800 - Rent')
                    insert_ph.append('%s')

                if has_created_from_banking:
                    insert_cols.append('created_from_banking')
                    insert_vals.append(True)
                    insert_ph.append('%s')

                if has_source_system:
                    insert_cols.append('source_system')
                    insert_vals.append('EMAIL+BANKING')
                    insert_ph.append('%s')

                if has_source_reference and src_ref:
                    insert_cols.append('source_reference')
                    insert_vals.append(src_ref)
                    insert_ph.append('%s')

                if has_source_hash:
                    insert_cols.append('source_hash')
                    insert_vals.append(src_hash)
                    insert_ph.append('%s')

                if 'description' in receipts_cols:
                    insert_cols.append('description')
                    insert_vals.append(desc)
                    insert_ph.append('%s')

                if has_business_flag:
                    if 'is_business_expense' in receipts_cols:
                        insert_cols.append('is_business_expense')
                    else:
                        insert_cols.append('business_expense')
                    insert_vals.append(True)
                    insert_ph.append('%s')

                insert_sql = f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({', '.join(insert_ph)})"

                if args.write:
                    cur.execute(insert_sql, insert_vals)
                    created += 1
                    print(f"CREATED (email-matched) receipt for {txn_date or ev_dt} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor}' | ev_id={ev_id}")
                else:
                    print(f"DRY-RUN would create (email-matched) receipt for {txn_date or ev_dt} ${amount:.2f} | bank_id={txn_id} | vendor='{vendor}' | ev_id={ev_id}")

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    print(f"Summary: created={created}, skipped_existing={skipped}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

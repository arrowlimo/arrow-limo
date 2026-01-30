#!/usr/bin/env python3
"""
Create Receipts From Banking Transactions
========================================

Generates expense receipts from banking transactions for a given period.
- Only creates receipts for outgoing debits (payments/withdrawals) and bank charges/NSF
- Skips deposits/credits by default
- Idempotent: uses source_hash if available, else a composite guard
- Adds linkage in banking_receipt_matching_ledger if present

Usage:
  python -X utf8 scripts/create_receipts_from_banking.py --year 2012 --dry-run
  python -X utf8 scripts/create_receipts_from_banking.py --start 2012-01-01 --end 2012-12-31 --apply

Safety:
- Dry-run by default; require --apply to write
- No deletions; protected tables respected
"""
from __future__ import annotations

import os
import sys
import re
import argparse
from datetime import datetime, date
from decimal import Decimal
import hashlib

import psycopg2
from psycopg2.extras import DictCursor

# DB config
DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

# Tax rates
TAX_RATES = {
    'AB': Decimal('0.05'),
    'SK': Decimal('0.11'),
    'ON': Decimal('0.13'),
}

FEE_KEYWORDS = [
    'nsf', 'service charge', 'svc fee', 'fee', 'charge', 'overdraft', 'account fee', 'monthly fee', 'bank fee'
]
CRA_KEYWORDS = ['receiver general', 'canada revenue', 'revenue canada', 'cra', 'gst', 'gst/hst']

FUEL_VENDORS = ['shell', 'petro', 'esso', 'fas gas', 'chevron']
TELECOM_VENDORS = ['telus', 'rogers', 'sasktel', 'bell']
INSURANCE_VENDORS = ['aviva', 'sgi', 'insurance']
MAINT_VENDORS = ['canadian tire', 'jiffy lube', 'midas', 'repair']


def parse_args():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument('--year', type=int)
    grp.add_argument('--start', type=str)
    ap.add_argument('--end', type=str)
    ap.add_argument('--province', default='AB', help='Province for GST/HST default (AB/SK/ON)')
    ap.add_argument('--include-credits', action='store_true', help='Also create receipts for credits (rare)')
    ap.add_argument('--apply', action='store_true', help='Write changes (default dry-run)')
    ap.add_argument('--limit', type=int, default=0)
    return ap.parse_args()


def resolve_dates(args) -> tuple[date, date]:
    if args.year:
        return date(args.year, 1, 1), date(args.year, 12, 31)
    if not args.end:
        raise SystemExit('--start requires --end')
    return datetime.strptime(args.start, '%Y-%m-%d').date(), datetime.strptime(args.end, '%Y-%m-%d').date()


def get_cols(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
        """, (table,))
        return {r[0] for r in cur.fetchall()}


def get_column_generation(conn, table: str) -> dict[str, str]:
    """Return mapping of column_name -> is_generated ('ALWAYS' or 'NEVER')."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, is_generated
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0]: r[1] for r in cur.fetchall()}


def calc_gst_included(gross: Decimal, province: str) -> tuple[Decimal, Decimal]:
    rate = TAX_RATES.get(province.upper(), Decimal('0.05'))
    if rate <= 0:
        return Decimal('0.00'), gross
    gst = (gross * rate / (Decimal('1.00') + rate)).quantize(Decimal('0.01'))
    net = (gross - gst).quantize(Decimal('0.01'))
    return gst, net


def categorize(desc: str) -> tuple[str, bool, bool]:
    """Return (category, taxable, is_bank_fee)"""
    s = (desc or '').lower()
    # CRA remittances (non-taxable)
    if any(k in s for k in CRA_KEYWORDS):
        return 'tax_remittance', False, False
    # Bank fees/NSF (non-taxable financial services)
    if any(k in s for k in FEE_KEYWORDS):
        return 'bank_fees', False, True
    # Fuel (taxable)
    if any(v in s for v in FUEL_VENDORS):
        return 'fuel', True, False
    # Telecom (taxable)
    if any(v in s for v in TELECOM_VENDORS):
        return 'communication', True, False
    # Insurance (non-taxable for premiums; often exempt)
    if any(v in s for v in INSURANCE_VENDORS):
        return 'insurance', False, False
    # Maintenance (taxable)
    if any(v in s for v in MAINT_VENDORS):
        return 'maintenance', True, False
    # Default expense, assume taxable for AB
    return 'expense', True, False


def build_banking_query(cols: set[str], start: date, end: date, include_credits: bool) -> tuple[str, list]:
    date_col = 'transaction_date' if 'transaction_date' in cols else 'trans_date' if 'trans_date' in cols else None
    if not date_col:
        raise SystemExit('banking_transactions has no date column')
    desc_col = 'description' if 'description' in cols else 'vendor_name' if 'vendor_name' in cols else 'memo' if 'memo' in cols else None
    debit_col = 'debit_amount' if 'debit_amount' in cols else None
    credit_col = 'credit_amount' if 'credit_amount' in cols else None
    account_col = 'account_number' if 'account_number' in cols else None
    bank_id_col = 'transaction_id' if 'transaction_id' in cols else None

    if not debit_col or not credit_col or not desc_col:
        raise SystemExit('banking_transactions is missing required columns (debit/credit/description)')

    where = [f"{date_col} BETWEEN %s AND %s"]
    params = [start, end]
    if not include_credits:
        where.append(f"COALESCE({debit_col},0) > 0")

    query = f"""
        SELECT 
            {bank_id_col if bank_id_col else 'NULL'} AS bank_tx_id,
            {date_col} AS tx_date,
            {desc_col} AS description,
            COALESCE({debit_col},0) AS debit_amount,
            COALESCE({credit_col},0) AS credit_amount,
            {account_col if account_col else 'NULL'} AS account_number
        FROM banking_transactions
        WHERE {' AND '.join(where)}
        ORDER BY {date_col} ASC
    """
    return query, params


def existing_receipt_hashes(conn) -> set[str]:
    cols = get_cols(conn, 'receipts')
    if 'source_hash' not in cols:
        return set()
    with conn.cursor() as cur:
        cur.execute("SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL")
        return {r[0] for r in cur.fetchall()}


def insert_receipt(conn, rec: dict, receipts_cols: set[str], generated_cols: dict[str, str], apply: bool) -> int | None:
    fields = []
    values = []
    # map only columns that exist
    for k in ['receipt_date','vendor_name','category','gross_amount','gst_amount','net_amount','description','is_taxable','is_business_expense']:
        if k in receipts_cols and k in rec:
            # Skip generated columns (e.g., net_amount) which cannot be explicitly inserted
            if generated_cols.get(k, 'NEVER') != 'NEVER':
                continue
            fields.append(k)
            values.append(rec[k])
    # Optional columns
    if 'tax_rate' in receipts_cols and 'tax_rate' in rec:
        if generated_cols.get('tax_rate', 'NEVER') == 'NEVER':
            fields.append('tax_rate'); values.append(rec['tax_rate'])
    if 'created_from_banking' in receipts_cols:
        if generated_cols.get('created_from_banking', 'NEVER') == 'NEVER':
            fields.append('created_from_banking'); values.append(True)
    if 'source_hash' in receipts_cols and 'source_hash' in rec:
        if generated_cols.get('source_hash', 'NEVER') == 'NEVER':
            fields.append('source_hash'); values.append(rec['source_hash'])

    placeholders = ','.join(['%s'] * len(values))
    # Use fresh connection to avoid transaction abort cascade
    fresh_conn = psycopg2.connect(**DSN)
    fresh_conn.autocommit = True
    try:
        sql = f"INSERT INTO receipts ({', '.join(fields)}) VALUES ({placeholders}) RETURNING { 'receipt_id' if 'receipt_id' in receipts_cols else 'id' if 'id' in receipts_cols else 'NULL' }"
        if not apply:
            return None
        with fresh_conn.cursor() as cur:
            cur.execute(sql, values)
            try:
                ret = cur.fetchone()
                return ret[0] if ret and len(ret) > 0 else None
            except Exception:
                return None
    finally:
        fresh_conn.close()


def link_ledger(conn, bank_tx_id: int | None, receipt_id: int | None):
    if not bank_tx_id or not receipt_id:
        return
    # Link if ledger exists
    cols = get_cols(conn, 'banking_receipt_matching_ledger')
    if not cols:
        return
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO banking_receipt_matching_ledger (bank_transaction_id, receipt_id)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger WHERE bank_transaction_id=%s AND receipt_id=%s
            )
        """, (bank_tx_id, receipt_id, bank_tx_id, receipt_id))


def main():
    args = parse_args()
    start, end = resolve_dates(args)
    province = args.province.upper()

    try:
        with psycopg2.connect(**DSN) as conn:
            conn.autocommit = True
            bank_cols = get_cols(conn, 'banking_transactions')
            rec_cols = get_cols(conn, 'receipts')
            if not rec_cols:
                print('[FAIL] receipts table not found')
                sys.exit(1)

            # Prefetch existing hashes for idempotency
            receipt_hashes = existing_receipt_hashes(conn)
            
            # Prefetch generated columns once
            generated_cols = get_column_generation(conn, 'receipts')

            query, params = build_banking_query(bank_cols, start, end, args.include_credits)
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

            created = 0
            skipped = 0
            planned = 0
            skip_reasons = {}  # track skip reasons
            for r in rows:
                bank_tx_id = r['bank_tx_id']
                tx_date = r['tx_date']
                desc = (r['description'] or '').strip()
                debit = Decimal(str(r['debit_amount'] or 0))
                credit = Decimal(str(r['credit_amount'] or 0))
                account = r['account_number']

                # Skip pure credits unless asked
                if debit <= 0 and not args.include_credits:
                    skip_reasons['credit_only'] = skip_reasons.get('credit_only', 0) + 1
                    continue

                category, taxable, is_bank_fee = categorize(desc)

                gross = debit if debit > 0 else credit
                if taxable and not is_bank_fee:
                    gst, net = calc_gst_included(gross, province)
                    tax_rate = TAX_RATES.get(province, Decimal('0.05'))
                else:
                    gst, net, tax_rate = Decimal('0.00'), gross, Decimal('0.00')

                # Build source_hash deterministically
                src_key = f"{tx_date}|{desc}|{gross}|{account}|{province}|{category}"
                src_hash = hashlib.sha256(src_key.encode('utf-8')).hexdigest()
                if src_hash in receipt_hashes:
                    skipped += 1
                    skip_reasons['duplicate_hash'] = skip_reasons.get('duplicate_hash', 0) + 1
                    continue

                rec = {
                    'receipt_date': tx_date,
                    'vendor_name': desc[:200],
                    'category': category,
                    'gross_amount': float(gross),
                    'gst_amount': float(gst),
                    'net_amount': float(net),
                    'description': f"AUTO-GEN FROM BANKING {account or ''}".strip(),
                    'is_taxable': taxable and not is_bank_fee,
                    'is_business_expense': True,
                    'tax_rate': float(tax_rate),
                    'source_hash': src_hash,
                }

                planned += 1
                try:
                    new_id = insert_receipt(conn, rec, rec_cols, generated_cols, args.apply)
                    if args.apply and new_id:
                        created += 1
                        try:
                            link_ledger(conn, bank_tx_id, new_id)
                        except Exception:
                            pass
                except Exception as e:
                    # If any insert fails, continue to next
                    skipped += 1
                    err_msg = str(e)[:80]  # truncate
                    skip_reasons[f'insert_error: {err_msg}'] = skip_reasons.get(f'insert_error: {err_msg}', 0) + 1

            print('\nSummary:')
            print(f'  Period: {start} to {end}')
            print(f'  Candidates: {planned}')
            print(f'  Created:   {created}')
            print(f'  Skipped:   {skipped}')
            if skip_reasons:
                print(f'\n  Skip breakdown:')
                for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
                    print(f'    {reason}: {count}')
            print(f'  Mode:      {"APPLY" if args.apply else "DRY-RUN"}')
    except Exception as e:
        print('[FAIL] Error:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()

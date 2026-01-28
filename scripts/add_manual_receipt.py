#!/usr/bin/env python3
"""
Add a manual expense receipt (schema-aware, dry-run by default)
==============================================================

Purpose: Insert a single expense receipt with proper GST-included handling and
notes for split payments. Designed for cases like a 2012 maintenance invoice
paid $100 cash + $258.38 debit (card ****0359), GST included $17.07.

Usage (dry-run):
  python -X utf8 scripts/add_manual_receipt.py \
    --date 2012-12-28 \
    --vendor "Choice Auto Electric Repair Ltd" \
    --category maintenance \
    --gross 358.38 \
    --gst 17.07 \
    --notes "Invoice IN00040877; Paid $100 cash + $258.38 debit (****0359); GST included"

To write:
  ... --write

Safety:
- Introspects receipts columns and only inserts what exists
- Dry-run by default (prints INSERT statement and values)
- No DELETEs, no updates
"""
from __future__ import annotations

import os
import sys
import argparse
from datetime import datetime
import psycopg2
import hashlib

DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    port=int(os.environ.get('DB_PORT', '5432')),
)


def get_columns(cur, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r[0] for r in cur.fetchall()}

def is_generated(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT is_generated
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name=%s
        """,
        (table, column),
    )
    row = cur.fetchone()
    if not row:
        return False
    return (row[0] or '').upper() == 'ALWAYS'


def coalesce_tax(gross: float, gst_opt: float | None, rate: float | None) -> tuple[float, float]:
    """Return (gst_amount, net_amount) using 'tax included' model if needed."""
    if gst_opt is not None:
        gst = float(gst_opt)
        net = float(gross) - gst
        return round(gst, 2), round(net, 2)
    # fallback: derive gst from rate if provided
    r = rate if rate is not None else 0.05
    gst = float(gross) * (r / (1 + r))
    net = float(gross) - gst
    return round(gst, 2), round(net, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True, help='Receipt date YYYY-MM-DD')
    ap.add_argument('--vendor', required=True)
    ap.add_argument('--category', default='maintenance')
    ap.add_argument('--gross', type=float, required=True)
    ap.add_argument('--gst', type=float, default=None, help='GST included amount (overrides rate calc)')
    ap.add_argument('--rate', type=float, default=0.05, help='GST/HST rate (used only if --gst omitted)')
    ap.add_argument('--notes', default='')
    ap.add_argument('--write', action='store_true', help='Apply insert (default dry-run)')
    args = ap.parse_args()

    try:
        # validate date
        dt = datetime.strptime(args.date, '%Y-%m-%d').date()
    except Exception as e:
        print('[FAIL] Invalid --date:', e)
        return 2

    gst_amount, net_amount = coalesce_tax(args.gross, args.gst, args.rate)

    with psycopg2.connect(**DSN) as conn:
        with conn.cursor() as cur:
            cols = get_columns(cur, 'receipts')
            if not cols:
                print('[FAIL] receipts table not found')
                return 1

            # Build insert parts based on available columns
            insert_cols = []
            values = []

            def add(col: str, val):
                insert_cols.append(col)
                values.append(val)

            # Common columns
            if 'receipt_date' in cols:
                add('receipt_date', dt)
            elif 'date' in cols:
                add('date', dt)
            else:
                print('[WARN] No date column found in receipts; inserting without date')

            if 'vendor_name' in cols:
                add('vendor_name', args.vendor)
            elif 'vendor' in cols:
                add('vendor', args.vendor)

            if 'category' in cols:
                add('category', args.category)

            # Amounts
            gross_col = None
            for c in ('gross_amount', 'amount', 'total'):
                if c in cols:
                    gross_col = c
                    break
            if gross_col:
                add(gross_col, round(float(args.gross), 2))

            if 'gst_amount' in cols:
                add('gst_amount', gst_amount)
            elif 'tax_amount' in cols:
                add('tax_amount', gst_amount)

            if 'net_amount' in cols:
                # Skip if generated always
                if not is_generated(cur, 'receipts', 'net_amount'):
                    add('net_amount', net_amount)

            if 'tax_rate' in cols and args.gst is None:
                add('tax_rate', args.rate)

            # Description / notes capturing split payment details
            desc_text = args.notes.strip()
            if desc_text and 'description' in cols:
                add('description', desc_text)
            elif desc_text and 'notes' in cols:
                add('notes', desc_text)

            if 'is_business_expense' in cols:
                add('is_business_expense', True)

            # Default created_at if present
            if 'created_at' in cols:
                add('created_at', datetime.now())

            # Deterministic unique source_hash if column exists (prevents unique collisions)
            if 'source_hash' in cols:
                desc_text = args.notes.strip()
                basis = f"MANUAL|{dt.isoformat()}|{args.vendor}|{args.category}|{round(float(args.gross),2)}|{gst_amount}|{desc_text}"
                h = hashlib.sha256(basis.encode('utf-8')).hexdigest()
                add('source_hash', h)

            # Optional provenance field
            if 'source_system' in cols:
                add('source_system', 'MANUAL_ENTRY')
            elif 'import_source' in cols:
                add('import_source', 'MANUAL_ENTRY')

            if not insert_cols:
                print('[FAIL] Nothing to insert (no compatible columns)')
                return 1

            placeholders = ','.join(['%s'] * len(values))
            sql = f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({placeholders}) RETURNING 1"

            if args.write:
                try:
                    cur.execute(sql, values)
                    conn.commit()
                    print('[OK] Inserted manual receipt:', {
                        'date': str(dt), 'vendor': args.vendor, 'category': args.category,
                        'gross': round(float(args.gross), 2), 'gst': gst_amount, 'net': net_amount
                    })
                except Exception as e:
                    # Retry without net_amount if that caused the error
                    conn.rollback()
                    msg = str(e).lower()
                    if 'net_amount' in msg and 'generated column' in msg:
                        try:
                            # remove net_amount from insert and values
                            filtered = [(c, v) for c, v in zip(insert_cols, values) if c != 'net_amount']
                            new_cols = [c for c, _ in filtered]
                            new_vals = [v for _, v in filtered]
                            placeholders2 = ','.join(['%s'] * len(new_vals))
                            sql2 = f"INSERT INTO receipts ({', '.join(new_cols)}) VALUES ({placeholders2}) RETURNING 1"
                            cur.execute(sql2, new_vals)
                            conn.commit()
                            print('[OK] Inserted manual receipt on retry (excluded net_amount)')
                        except Exception as e2:
                            conn.rollback()
                            print('[FAIL] Insert failed (retry):', e2)
                            return 1
                    else:
                        print('[FAIL] Insert failed:', e)
                        return 1
            else:
                print('🔎 Dry-run. Would insert:')
                print('  SQL:', sql)
                print('  Values:', values)
                print('  Summary:', {
                    'date': str(dt), 'vendor': args.vendor, 'category': args.category,
                    'gross': round(float(args.gross), 2), 'gst': gst_amount, 'net': net_amount
                })
    return 0


if __name__ == '__main__':
    sys.exit(main())

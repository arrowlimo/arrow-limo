#!/usr/bin/env python3
"""
Create receipts for unlinked banking fee/NSF transactions and link them back.

- Dry-run by default; use --write to persist.
- Targets banking_transactions where receipt_id IS NULL and description matches fee/NSF patterns and signed amount < 0.
- Inserts into receipts only the columns that actually exist (schema-introspected), with conservative defaults:
  - vendor_name: banking vendor_extracted or 'Bank'
  - receipt_date: transaction_date
  - gross_amount/amount: absolute value of debit (expense)
  - gst_amount/net_amount/tax_rate/is_taxable: set to 0 / False when present
  - category: 'bank_fees' or 'nsf_fee' based on matched pattern
  - description: banking description + transaction_id reference
- After insert, updates banking_transactions.receipt_id to the new receipt.

Usage:
  python -X utf8 scripts/create_missing_bank_fee_receipts.py [--write] [--limit 500]
"""

import os
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

FEE_PATTERNS = [
    'fee', 'fees', 'service charge', 'svc chg', 'monthly fee', 'account fee', 'bank charge',
    'overdraft', 'network fee', 'e-transfer network fee', 'atm fee'
]
NSF_PATTERNS = [
    'nsf', 'non sufficient', 'insufficient funds', 'returned item'
]


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    return [r['column_name'] for r in cur.fetchall()]


def amount_expr(cols):
    if 'debit_amount' in cols and 'credit_amount' in cols:
        return '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif 'amount' in cols:
        return 'amount'
    return '0'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply inserts/links instead of dry-run')
    parser.add_argument('--limit', type=int, default=500, help='Max number of receipts to create this run')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Introspect schemas
    bt_cols = get_columns(cur, 'banking_transactions')
    rc_cols = get_columns(cur, 'receipts')

    amt_expr = amount_expr(bt_cols)

    like_fee = " OR ".join(["LOWER(description) LIKE %s" for _ in FEE_PATTERNS])
    like_nsf = " OR ".join(["LOWER(description) LIKE %s" for _ in NSF_PATTERNS])
    fee_params = [f"%{p.lower()}%" for p in FEE_PATTERNS]
    nsf_params = [f"%{p.lower()}%" for p in NSF_PATTERNS]

    # Gather candidates (fees + nsf), negative amounts only, unlinked
    cur.execute(
        f"""
        WITH fee_candidates AS (
            SELECT *, 'bank_fees'::text AS category_match
            FROM banking_transactions
            WHERE receipt_id IS NULL
              AND ({amt_expr}) < 0
              AND ({like_fee})
        ), nsf_candidates AS (
            SELECT *, 'nsf_fee'::text AS category_match
            FROM banking_transactions
            WHERE receipt_id IS NULL
              AND ({amt_expr}) < 0
              AND ({like_nsf})
        ), unioned AS (
            SELECT * FROM fee_candidates
            UNION ALL
            SELECT * FROM nsf_candidates
        )
        SELECT transaction_id, transaction_date, description, vendor_extracted, vendor_truncated,
               {amt_expr} AS signed_amount, category_match
        FROM unioned
        ORDER BY transaction_date DESC
        LIMIT %s
        """,
        [*fee_params, *nsf_params, args.limit]
    )
    rows = cur.fetchall()

    if not rows:
        print('No missing fee/NSF receipts to create. PASS (no-op)')
        return

    print(f"Creation candidates: {len(rows)} (limit {args.limit})")

    # Prepare insert column set (only what's available)
    colmap = []
    if 'vendor_name' in rc_cols:
        colmap.append('vendor_name')
    if 'receipt_date' in rc_cols:
        colmap.append('receipt_date')
    amount_col = 'gross_amount' if 'gross_amount' in rc_cols else ('amount' if 'amount' in rc_cols else None)
    if amount_col:
        colmap.append(amount_col)
    if 'gst_amount' in rc_cols:
        colmap.append('gst_amount')
    if 'net_amount' in rc_cols:
        colmap.append('net_amount')
    if 'tax_rate' in rc_cols:
        colmap.append('tax_rate')
    if 'is_taxable' in rc_cols:
        colmap.append('is_taxable')
    if 'category' in rc_cols:
        colmap.append('category')
    if 'description' in rc_cols:
        colmap.append('description')
    if 'bank_id' in rc_cols:
        colmap.append('bank_id')
    # Provenance/idempotency columns
    if 'source_hash' in rc_cols:
        colmap.append('source_hash')
    if 'source' in rc_cols:
        colmap.append('source')
    if 'source_reference' in rc_cols:
        colmap.append('source_reference')

    # Determine primary key column for RETURNING
    pk_col = 'receipt_id' if 'receipt_id' in rc_cols else ('id' if 'id' in rc_cols else None)

    # Build insert SQL
    insert_cols_sql = ", ".join(colmap)
    placeholders = ", ".join(["%s"] * len(colmap))
    insert_sql = f"INSERT INTO receipts ({insert_cols_sql}) VALUES ({placeholders})"
    if 'source_hash' in colmap:
        # Idempotent upsert by source_hash
        insert_sql += " ON CONFLICT (source_hash) DO UPDATE SET receipt_date = EXCLUDED.receipt_date"
    if pk_col:
        insert_sql += f" RETURNING {pk_col}"

    created = 0

    for r in rows:
        vendor = r['vendor_extracted'] or r['vendor_truncated'] or 'Bank'
        date = r['transaction_date']
        amt = float(r['signed_amount'] or 0)
        expense = abs(amt)  # positive expense amount
        category = r['category_match']
        desc = f"{r['description']} (tx:{r['transaction_id']})"

        values = []
        for c in colmap:
            if c == 'vendor_name':
                values.append(vendor)
            elif c == 'receipt_date':
                values.append(date)
            elif c == 'gross_amount' or c == 'amount':
                values.append(expense)
            elif c == 'gst_amount':
                values.append(0)
            elif c == 'net_amount':
                values.append(expense)
            elif c == 'tax_rate':
                values.append(0)
            elif c == 'is_taxable':
                values.append(False)
            elif c == 'category':
                values.append(category)
            elif c == 'description':
                values.append(desc)
            elif c == 'bank_id':
                # Link to banking row if receipts has bank_id column and banking_transactions has transaction_id as integer
                # Not all schemas have this link, but when available it's useful for provenance
                values.append(r['transaction_id'])
            elif c == 'source_hash':
                # Deterministic idempotent key
                values.append(f"bank_auto:{r['transaction_id']}")
            elif c == 'source':
                values.append('banking_auto')
            elif c == 'source_reference':
                values.append(str(r['transaction_id']))
            else:
                values.append(None)

        if not args.write:
            created += 1
            continue

        # Insert receipt
        cur.execute(insert_sql, values)
        if pk_col:
            new_id = cur.fetchone()[pk_col]
        else:
            new_id = None

        # Update banking linkage
        if new_id is not None:
            cur.execute(
                "UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
                (new_id, r['transaction_id'])
            )
        else:
            # Fallback: try linking by finding the most recent receipt matching our vendor/date/amount
            # Only attempt if receipts has these columns
            where_clauses = []
            params = []
            if 'vendor_name' in rc_cols:
                where_clauses.append('vendor_name = %s')
                params.append(vendor)
            if 'receipt_date' in rc_cols:
                where_clauses.append('receipt_date = %s')
                params.append(date)
            if 'gross_amount' in rc_cols:
                where_clauses.append('gross_amount = %s')
                params.append(expense)
            elif 'amount' in rc_cols:
                where_clauses.append('amount = %s')
                params.append(expense)

            if where_clauses:
                cur.execute(
                    f"SELECT COALESCE((SELECT receipt_id FROM receipts WHERE {' AND '.join(where_clauses)} ORDER BY created_at DESC NULLS LAST LIMIT 1), (SELECT id FROM receipts WHERE {' AND '.join(where_clauses)} ORDER BY created_at DESC NULLS LAST LIMIT 1)) AS rid",
                    params
                )
                row = cur.fetchone()
                rid = row['rid'] if row else None
                if rid is not None:
                    cur.execute(
                        "UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
                        (rid, r['transaction_id'])
                    )
        created += 1

    if args.write:
        conn.commit()

    print(f"Receipts {'to be created' if not args.write else 'created'}: {created}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()

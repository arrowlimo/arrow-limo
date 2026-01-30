#!/usr/bin/env python3
"""
Ensure an account_number exists in the referenced account table for banking_transactions.account_number.

Usage:
  python -X utf8 scripts/ensure_banking_account.py --account 903990106011 [--create]

This script:
- Detects the foreign key from public.banking_transactions.account_number to a referenced table
- Checks whether the provided account number exists in that referenced table
- With --create, attempts to insert a minimal row (account_number only) if possible

Safety:
- Read-only unless --create provided
- If referenced table has other NOT NULL columns without defaults, creation will fail safely
"""
from __future__ import annotations
import argparse
import os
import psycopg2


def get_conn():
    host = os.environ.get('DB_HOST', 'localhost')
    dbname = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def get_ref_table(cur):
    cur.execute(
        """
        SELECT c.confrelid::regclass::text AS ref_table,
               pg_get_constraintdef(c.oid) AS def
        FROM pg_constraint c
        CROSS JOIN LATERAL unnest(c.conkey) AS k(attnum)
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
        WHERE c.contype='f'
          AND c.conrelid='public.banking_transactions'::regclass
          AND a.attname='account_number'
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return row[0], row[1]


def has_account(cur, ref_table: str, account: str) -> bool:
    cur.execute(f"SELECT 1 FROM {ref_table} WHERE account_number = %s LIMIT 1", (account,))
    return cur.fetchone() is not None


def required_no_default_columns(cur, ref_table: str):
    # Check columns that are NOT NULL without default; if only account_number, we can insert minimal
    cur.execute(
        """
        SELECT column_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name = %s
        """,
        (ref_table.split('.')[-1],)
    )
    rows = cur.fetchall()
    must = [r[0] for r in rows if r[1]=='NO' and (r[2] is None)]
    return must

def create_account(cur, ref_table: str, account: str, name: str | None = None, acc_type: str | None = None, last4: str | None = None) -> bool:
    try:
        cols = ['account_number']
        vals = [account]
        if name is not None:
            cols.append('account_name'); vals.append(name)
        if acc_type is not None:
            cols.append('account_type'); vals.append(acc_type)
        if last4 is not None:
            cols.append('last4'); vals.append(last4)
        ph = ','.join(['%s']*len(vals))
        cur.execute(f"INSERT INTO {ref_table} (" + ','.join(cols) + ") VALUES (" + ph + ")", tuple(vals))
        return True
    except Exception as e:
        print(f"ERROR: Failed to create account in {ref_table}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', required=True)
    ap.add_argument('--create', action='store_true')
    ap.add_argument('--name', help='Account name to insert when creating')
    ap.add_argument('--type', dest='acc_type', help='Account type to insert when creating (e.g., checking)')
    ap.add_argument('--last4', help='Last 4 digits to insert when creating')
    args = ap.parse_args()

    conn = get_conn(); conn.autocommit = False
    cur = conn.cursor()
    ref_table, fkdef = get_ref_table(cur)
    if not ref_table:
        print("No FK reference found from banking_transactions.account_number; nothing to ensure.")
        cur.close(); conn.close(); return
    print(f"FK target: {ref_table} | def: {fkdef}")

    if has_account(cur, ref_table, args.account):
        print(f"Present: account_number {args.account} exists in {ref_table}")
        cur.close(); conn.close(); return

    print(f"Missing: account_number {args.account} not found in {ref_table}")
    if not args.create:
        print("Run with --create to attempt minimal insertion (account_number only).")
        cur.close(); conn.close(); return

    must = required_no_default_columns(cur, ref_table)
    # Normalize
    must_norm = [m.lower() for m in must]
    if must_norm != ['account_number']:
        print(f"Required (NOT NULL, no default) in {ref_table}: {must}")
        # Verify we have provided required columns
        provided = {'account_number': True,
                    'account_name': args.name is not None,
                    'account_type': args.acc_type is not None,
                    'last4': args.last4 is not None}
        missing = [m for m in must_norm if not provided.get(m, False)]
        if missing:
            print(f"Cannot create: missing required fields for {ref_table}: {missing}. Provide with --name/--type/--last4.")
            conn.rollback(); cur.close(); conn.close(); return

    ok = create_account(cur, ref_table, args.account, args.name, args.acc_type, args.last4)
    if ok:
        conn.commit(); print(f"Created account_number {args.account} in {ref_table}")
    else:
        conn.rollback(); print("Creation aborted.")
    cur.close(); conn.close()


if __name__ == '__main__':
    main()

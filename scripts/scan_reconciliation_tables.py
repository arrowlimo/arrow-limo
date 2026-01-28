#!/usr/bin/env python3
"""
Scan almsdata (public schema) for tables/views with data and identify reconciliation/linking candidates.
Outputs:
- reports/reconciliation_table_inventory.csv (one row per table/view with counts and signals)
- reports/reconciliation_signals_details.csv (detailed matched signals per object)

Signals considered:
- Name-based keywords: reconcile, reconciliation, match, matches, linking, links, reference, payout
- Column-based keywords: charter_id, reserve_number, payment_id, payment_key, reconciliation_status, calculated_balance,
  overpaid_amount, credit_applied_to_charter, credit_carried_forward
- Foreign keys pointing to payments or charters

Note: Uses pg_stat_user_tables for fast row approximations on tables. For views, tries SELECT 1 FROM view LIMIT 1 to detect presence.
"""
import os
import csv
from typing import List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')
INV_CSV = 'l:/limo/reports/reconciliation_table_inventory.csv'
SIG_CSV = 'l:/limo/reports/reconciliation_signals_details.csv'

NAME_KEYWORDS = [
    'reconcile', 'reconciliation', 'match', 'matches', 'link', 'links', 'linking', 'reference', 'references', 'payout'
]
COL_KEYWORDS = [
    'charter_id', 'reserve_number', 'payment_id', 'payment_key', 'reconciliation_status', 'calculated_balance',
    'overpaid_amount', 'credit_applied_to_charter', 'credit_carried_forward'
]

REF_TABLES = ['payments', 'charters']


def get_conn():
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    conn.autocommit = True
    return conn


def fetch_objects(cur) -> List[Dict]:
    cur.execute(
        """
        SELECT table_schema, table_name, table_type
          FROM information_schema.tables
         WHERE table_schema = 'public'
         ORDER BY table_name
        """
    )
    return list(cur.fetchall())


def fetch_columns(cur, schema: str, table: str) -> List[str]:
    cur.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = %s AND table_name = %s
         ORDER BY ordinal_position
        """,
        (schema, table)
    )
    return [r['column_name'] for r in cur.fetchall()]


def fetch_fk_refs(cur, schema: str, table: str) -> List[Dict]:
    cur.execute(
        """
        SELECT tc.constraint_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
          FROM information_schema.table_constraints AS tc
          JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
          JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
           AND ccu.table_schema = tc.table_schema
         WHERE tc.table_schema = %s AND tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'
        """,
        (schema, table)
    )
    return list(cur.fetchall())


def fetch_table_estimated_count(cur, schema: str, table: str) -> int:
    cur.execute(
        """
        SELECT COALESCE(s.n_live_tup,0) AS est
          FROM pg_stat_user_tables s
          JOIN pg_class c ON c.relname = s.relname
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s
        """,
        (schema, table)
    )
    row = cur.fetchone()
    return int(row['est']) if row else 0


def view_has_rows(cur, schema: str, view: str) -> int:
    try:
        cur.execute(f"SELECT 1 FROM {schema}.\"{view}\" LIMIT 1")
        return 1 if cur.fetchone() else 0
    except Exception:
        return -1  # query failed


def main():
    os.makedirs(os.path.dirname(INV_CSV), exist_ok=True)
    signals_rows = []
    inv_rows = []

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            objs = fetch_objects(cur)
            for obj in objs:
                schema = obj['table_schema']
                name = obj['table_name']
                ttype = obj['table_type']  # BASE TABLE or VIEW
                try:
                    cols = fetch_columns(cur, schema, name)
                except Exception:
                    cols = []
                try:
                    fks = fetch_fk_refs(cur, schema, name)
                except Exception:
                    fks = []
                try:
                    if ttype == 'BASE TABLE':
                        row_count = fetch_table_estimated_count(cur, schema, name)
                    else:
                        row_count = view_has_rows(cur, schema, name)
                except Exception:
                    row_count = -1

                name_hits = [kw for kw in NAME_KEYWORDS if kw in name.lower()]
                col_hits = [kw for kw in COL_KEYWORDS if kw in [c.lower() for c in cols]]
                fk_hits = [fk for fk in fks if fk.get('foreign_table_name') in REF_TABLES]
                recon_candidate = bool(name_hits or col_hits or fk_hits)

                inv_rows.append({
                    'schema': schema,
                    'name': name,
                    'type': ttype,
                    'row_indicator': row_count,
                    'has_data': (row_count > 0),
                    'signals_name_keywords': ','.join(name_hits),
                    'signals_col_keywords': ','.join(col_hits),
                    'signals_fk_refs': ';'.join(f"{fk.get('column_name','')}->{fk.get('foreign_table_name','')}.{fk.get('foreign_column_name','')}" for fk in fk_hits),
                    'reconciliation_linking_candidate': recon_candidate,
                })

                if name_hits:
                    for kw in name_hits:
                        signals_rows.append({'schema': schema, 'name': name, 'type': ttype, 'signal_type': 'name', 'signal': kw})
                if col_hits:
                    for kw in col_hits:
                        signals_rows.append({'schema': schema, 'name': name, 'type': ttype, 'signal_type': 'column', 'signal': kw})
                if fk_hits:
                    for fk in fk_hits:
                        signals_rows.append({'schema': schema, 'name': name, 'type': ttype, 'signal_type': 'fk', 'signal': f"{fk.get('column_name','')}->{fk.get('foreign_table_name','')}.{fk.get('foreign_column_name','')}"})

    # Write CSVs
    with open(INV_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(inv_rows[0].keys()) if inv_rows else [
            'schema','name','type','row_indicator','has_data','signals_name_keywords','signals_col_keywords','signals_fk_refs','reconciliation_linking_candidate'
        ])
        w.writeheader()
        for r in inv_rows:
            w.writerow(r)

    with open(SIG_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['schema','name','type','signal_type','signal'])
        w.writeheader()
        for r in signals_rows:
            w.writerow(r)

    print('Inventory written to:', INV_CSV)
    print('Signals written to   :', SIG_CSV)
    print('Candidates found     :', sum(1 for r in inv_rows if r['reconciliation_linking_candidate']))


if __name__ == '__main__':
    main()

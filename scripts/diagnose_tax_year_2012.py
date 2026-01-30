#!/usr/bin/env python3
"""
Diagnostic for 2012 tax-year zeros
----------------------------------
Checks:
- Table existence and columns for receipts, unified_general_ledger, banking_transactions
- Date column chosen and row counts for 2012
- GST indicators in GL (account_name like %GST%) and amounts
- Sample rows for verification

Safe/read-only.
"""
import os
import psycopg2
from psycopg2.extras import DictCursor

DSN = dict(
    host=os.environ.get('DB_HOST','localhost'),
    database=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','***REDACTED***'),
    port=int(os.environ.get('DB_PORT','5432')),
)

TABLES = ['receipts','unified_general_ledger','banking_transactions']


def columns(conn, table):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
        """, (table,))
        return cur.fetchall()


def pick_date(cols):
    names = [c[0] for c in cols]
    for cand in ['transaction_date','date','receipt_date','posting_date','created_at']:
        if cand in names:
            return cand
    return None


def count_year(conn, table, date_col, year):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE EXTRACT(YEAR FROM {date_col})=%s", (year,))
        return cur.fetchone()[0]


def sample_rows(conn, table, date_col, year, where_extra='', limit=5):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            f"SELECT * FROM {table} WHERE EXTRACT(YEAR FROM {date_col})=%s {where_extra} ORDER BY {date_col} ASC LIMIT {limit}",
            (year,)
        )
        return cur.fetchall()


def main():
    print('Connecting to DB...', DSN['host'], DSN['database'])
    with psycopg2.connect(**DSN) as conn:
        for t in TABLES:
            print('\n=== TABLE:', t, '===')
            cols = columns(conn, t)
            if not cols:
                print('  - Not found')
                continue
            print('  - Columns:', ', '.join(f"{c[0]}" for c in cols))
            date_col = pick_date(cols)
            print('  - Date column chosen:', date_col)
            if not date_col:
                print('  - No usable date column; skipping counts')
                continue
            try:
                c2012 = count_year(conn, t, date_col, 2012)
                print('  - 2012 rows:', c2012)
            except Exception as e:
                print('  - Count failed:', e)
                continue
            try:
                rows = sample_rows(conn, t, date_col, 2012)
                print('  - Sample rows (first up to 5):', len(rows))
                for r in rows:
                    print('    •', dict(r))
            except Exception as e:
                print('  - Sample failed:', e)

        # GST focus in GL
        print('\n=== GST IN GL (by account_name like %GST%) ===')
        cols = columns(None, 'unified_general_ledger')  # placeholder
        # Re-query to get names for GL
        with psycopg2.connect(**DSN) as c2:
            gl_cols = columns(c2, 'unified_general_ledger')
            names = [c[0] for c in gl_cols]
            acc = 'account_name' if 'account_name' in names else None
            debit = 'debit_amount' if 'debit_amount' in names else None
            credit = 'credit_amount' if 'credit_amount' in names else None
            date_col = 'transaction_date' if 'transaction_date' in names else None
            if not (acc and debit and credit and date_col):
                print('  - Missing expected columns in GL; acc/debit/credit/date needed')
            else:
                with c2.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT 
                          COALESCE(SUM(CASE WHEN {acc} ILIKE '%GST%' THEN {credit} ELSE 0 END),0) AS credits,
                          COALESCE(SUM(CASE WHEN {acc} ILIKE '%GST%' THEN {debit}  ELSE 0 END),0) AS debits
                        FROM unified_general_ledger
                        WHERE EXTRACT(YEAR FROM {date_col})=2012
                        """
                    )
                    row = cur.fetchone()
                    print('  - GST credits (collected):', row[0])
                    print('  - GST debits  (ITCs):    ', row[1])

        # CRA in banking
        print('\n=== CRA PAYMENTS IN BANKING ===')
        with psycopg2.connect(**DSN) as c3:
            bcols = columns(c3, 'banking_transactions')
            bnames = [c[0] for c in bcols]
            date_col = 'transaction_date' if 'transaction_date' in bnames else None
            desc = 'description' if 'description' in bnames else ( 'vendor_name' if 'vendor_name' in bnames else None )
            debit = 'debit_amount' if 'debit_amount' in bnames else None
            if not (date_col and desc and debit):
                print('  - Missing banking key columns')
            else:
                with c3.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT COUNT(*), COALESCE(SUM({debit}),0)
                        FROM banking_transactions
                        WHERE EXTRACT(YEAR FROM {date_col})=2012
                          AND ({desc} ILIKE '%receiver general%' OR {desc} ILIKE '%revenue canada%' OR {desc} ILIKE '%canada revenue%' OR {desc} ILIKE '%cra%' OR {desc} ILIKE '%gst%')
                        """
                    )
                    cnt, amt = cur.fetchone()
                    print('  - Matches:', cnt, '  Total paid:', amt)

if __name__ == '__main__':
    main()

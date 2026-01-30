"""
2012 Receipts↔Banking heuristic matching coverage.
- Attempts to match receipts to banking_transactions by same date and amount (GST included model).
- Reports counts of matched vs unmatched and sample unmatched vendors.
"""
import os
import psycopg2
from datetime import date

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
}

YEAR=2012

def build_sql(id_col: str, vendor_col: str, desc_col: str):
    match_sql = f'''
    WITH rc AS (
      SELECT 
        r.{id_col} AS receipt_id,
        r.receipt_date,
        r.gross_amount,
        COALESCE(r.{vendor_col}, '') AS vendor_name,
        COALESCE(r.{desc_col}, '') AS description
      FROM receipts r
      WHERE r.receipt_date >= %s AND r.receipt_date < %s
    ),
    mt as (
      SELECT rc.receipt_id,
             EXISTS (
               SELECT 1 FROM banking_transactions b
               WHERE b.transaction_date = rc.receipt_date
                 AND (
                   (b.debit_amount IS NOT NULL AND ABS(b.debit_amount - rc.gross_amount) < 0.01)
                   OR (b.credit_amount IS NOT NULL AND ABS(b.credit_amount - rc.gross_amount) < 0.01)
                 )
             ) AS matched
      FROM rc
    )
    SELECT 
      COUNT(*) AS receipts,
      COUNT(*) FILTER (WHERE matched) AS matched,
      COUNT(*) FILTER (WHERE NOT matched) AS unmatched
    FROM mt
    '''

    sample_sql = f'''
    WITH rc AS (
      SELECT 
        r.{id_col} AS receipt_id,
        r.receipt_date,
        r.gross_amount,
        COALESCE(r.{vendor_col}, '') AS vendor_name,
        COALESCE(r.{desc_col}, '') AS description
      FROM receipts r
      WHERE r.receipt_date >= %s AND r.receipt_date < %s
    ),
    mt as (
      SELECT rc.*,
             EXISTS (
               SELECT 1 FROM banking_transactions b
               WHERE b.transaction_date = rc.receipt_date
                 AND (
                   (b.debit_amount IS NOT NULL AND ABS(b.debit_amount - rc.gross_amount) < 0.01)
                   OR (b.credit_amount IS NOT NULL AND ABS(b.credit_amount - rc.gross_amount) < 0.01)
                 )
             ) AS matched
      FROM rc
    )
    SELECT receipt_id, receipt_date, gross_amount, vendor_name, description
    FROM mt
    WHERE NOT matched
    ORDER BY receipt_date
    LIMIT 25
    '''
    return match_sql, sample_sql

def main():
    s,e = date(YEAR,1,1), date(YEAR+1,1,1)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # Introspect receipts columns
    cur.execute("""
      SELECT column_name FROM information_schema.columns
      WHERE table_name = 'receipts'
    """)
    cols = {r[0] for r in cur.fetchall()}
    id_col = 'receipt_id' if 'receipt_id' in cols else ('id' if 'id' in cols else None)
    vendor_col = 'vendor_name' if 'vendor_name' in cols else ('vendor_extracted' if 'vendor_extracted' in cols else 'category')
    desc_col = 'description' if 'description' in cols else ('notes' if 'notes' in cols else 'category')
    if not id_col:
      raise RuntimeError('No suitable id column in receipts (expected receipt_id or id)')

    MATCH_SQL, SAMPLE_UNMATCHED_SQL = build_sql(id_col, vendor_col, desc_col)

    cur.execute(MATCH_SQL, (s,e))
    r = cur.fetchone()
    print(f"Receipts 2012: {r[0]} | matched to banking: {r[1]} | unmatched: {r[2]}")

    if r[2] > 0:
        print("\nSample unmatched receipts:")
        print(f"{'ID':<8} {'Date':<10} {'Amount':>10} Vendor / Desc")
        print('-'*70)
        try:
            cur.execute(SAMPLE_UNMATCHED_SQL, (s,e))
            rows = cur.fetchall()
            for x in rows:
                print(f"{x[0]:<8} {x[1]} {x[2]:>10.2f} {x[3] or ''} | { (x[4] or '')[:50] }")
        except Exception as ex:
            print(f"Could not fetch sample unmatched due to: {ex}")

    cur.close(); conn.close()

if __name__=='__main__':
    main()

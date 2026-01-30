"""
Scan LMS (Access DB) for Reserve rows where payment type indicates promo/trade.
- Tries to connect to L:\\limo\\lms.mdb using Access ODBC driver
- Exports CSV with key fields
- Falls back to Postgres 'charters.payment_method' contains promo/trade if Access not available
"""
import os
import csv

REPORTS_DIR = os.path.join(os.getcwd(), 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

LMS_CANDIDATE_PATHS = [
    r'L:\\limo\\lms.mdb',
    r'L:\\limo\\backups\\lms.mdb',
    r'L:\\limo\\backup\\lms.mdb'
]

def try_access():
    try:
        import pyodbc
    except Exception as e:
        print(f"pyodbc not available: {e}")
        return None, None
    target_path = None
    for p in LMS_CANDIDATE_PATHS:
        if os.path.exists(p):
            target_path = p
            break
    if target_path is None:
        print("No LMS .mdb file found in candidate paths:")
        for p in LMS_CANDIDATE_PATHS:
            print("  -", p)
        return None, None
    # Try common Access drivers
    drivers = [
        '{Microsoft Access Driver (*.mdb, *.accdb)}',
        '{Microsoft Access Driver (*.mdb)}',
    ]
    conn = None
    last_err = None
    for d in drivers:
        conn_str = f'DRIVER={d};DBQ={target_path};'
        try:
            conn = pyodbc.connect(conn_str)
            print(f"Connected to LMS via {d} at {target_path}")
            break
        except Exception as e:
            last_err = e
    if conn is None:
        print(f"Failed to connect to LMS via ODBC: {last_err}")
        return None, None
    cur = conn.cursor()
    return conn, cur

def lms_columns(cur, table):
    cols = []
    try:
        for c in cur.columns(table=table):
            cols.append(c.column_name)
    except Exception:
        pass
    return [c for c in cols]

def export_lms_promo_trade():
    conn, cur = try_access()
    if conn is None:
        return 0
    # Build column list safely
    reserve_cols = lms_columns(cur, 'Reserve')
    want = ['Reserve_No','Account_No','PU_Date','Rate','Balance','Deposit','Pymt_Type','Vehicle','Name','Notes']
    select_cols = [c for c in want if c in reserve_cols]
    if not select_cols:
        select_cols = reserve_cols or ['Reserve_No','Account_No']
    sel = ', '.join(select_cols)
    # Query for promo/trade in Pymt_Type or Notes if exists
    where_parts = []
    if 'Pymt_Type' in reserve_cols:
        where_parts.append("Pymt_Type LIKE '%promo%' OR Pymt_Type LIKE '%trade%' OR UCASE(Pymt_Type) IN ('PROMO','TRADE')")
    if 'Notes' in reserve_cols:
        where_parts.append("Notes LIKE '%promo%' OR Notes LIKE '%trade%' OR Notes LIKE '%certificate%' OR Notes LIKE '%auction%'")
    where_clause = ' OR '.join(where_parts) or '1=0'
    sql = f"SELECT {sel} FROM Reserve WHERE {where_clause} ORDER BY PU_Date DESC"
    try:
        cur.execute(sql)
        rows = cur.fetchall()
    except Exception as e:
        print(f"LMS query failed: {e}")
        rows = []
    out_path = os.path.join(REPORTS_DIR, 'lms_promo_trade_reserve.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(select_cols)
        for r in rows:
            w.writerow(list(r))
    print(f"Wrote {len(rows)} LMS Reserve promo/trade rows to {out_path}")
    cur.close(); conn.close()
    return len(rows)

def export_pg_charters_fallback():
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    # Build fallback by joining payments for payment_method since charters table has no payment_method column.
    cur.execute("""
        WITH base AS (
            SELECT c.charter_id, c.charter_date, c.reserve_number, c.client_id, c.rate, c.deposit, c.balance,
                   c.booking_notes, c.client_notes, c.notes
            FROM charters c
            WHERE COALESCE(c.status,'') NOT IN ('cancelled','Cancelled')
        ), pay AS (
            SELECT p.charter_id,
                   STRING_AGG(DISTINCT LOWER(TRIM(p.payment_method)),'; ') AS methods,
                   BOOL_OR(LOWER(COALESCE(p.payment_method,'')) LIKE '%promo%') AS has_promo,
                   BOOL_OR(LOWER(COALESCE(p.payment_method,'')) LIKE '%trade%') AS has_trade
            FROM payments p
            GROUP BY p.charter_id
        )
        SELECT b.charter_date, b.reserve_number, b.client_id, b.rate, b.deposit, b.balance,
               COALESCE(pay.methods,'') AS payment_methods,
               LEFT(COALESCE(b.booking_notes,''),200) AS booking_excerpt,
               LEFT(COALESCE(b.client_notes,''),200) AS client_excerpt,
               LEFT(COALESCE(b.notes,''),200) AS notes_excerpt
        FROM base b
        LEFT JOIN pay USING (charter_id)
        WHERE (
            LOWER(COALESCE(b.booking_notes,'')) LIKE '%promo%' OR
            LOWER(COALESCE(b.booking_notes,'')) LIKE '%trade%' OR
            LOWER(COALESCE(b.client_notes,'')) LIKE '%promo%' OR
            LOWER(COALESCE(b.client_notes,'')) LIKE '%trade%' OR
            LOWER(COALESCE(b.notes,'')) LIKE '%promo%' OR
            LOWER(COALESCE(b.notes,'')) LIKE '%trade%' OR
            has_promo OR has_trade
        )
        ORDER BY b.charter_date DESC;
    """)
    rows = cur.fetchall()
    out_path = os.path.join(REPORTS_DIR, 'pg_charters_promo_trade_fallback.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['charter_date','reserve_number','client_id','rate','deposit','balance','payment_methods','booking_excerpt','client_excerpt','notes_excerpt'])
        for r in rows:
            out = [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]]
            w.writerow([x if x is not None else '' for x in out])
    print(f"Wrote {len(rows)} Postgres charters promo/trade rows to {out_path}")
    cur.close(); conn.close()

if __name__ == '__main__':
    count = export_lms_promo_trade()
    # Always also do the fallback for cross-check
    export_pg_charters_fallback()

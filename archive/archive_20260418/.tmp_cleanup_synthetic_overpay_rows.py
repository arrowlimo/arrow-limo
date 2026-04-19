import pandas as pd
import psycopg2
from psycopg2 import sql
from datetime import datetime
from pathlib import Path

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
OVERPAY_CSV = r"L:\limo\reports\overpaid_analysis_2012_2017_20260417_213945.csv"
REPORT_DIR = Path(r"L:\limo\reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

SYNTHETIC_NOTES = [
    'LMS-verified balancing payment - 2012 import gap',
    'Backfilled from charter_payments',
]


def find_referenced_payment_ids(conn, payment_ids):
    if not payment_ids:
        return set()
    ref_meta_sql = """
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_name = 'payments'
          AND ccu.column_name = 'payment_id'
            AND tc.table_name NOT IN ('charter_payments')
    """
    refs = pd.read_sql_query(ref_meta_sql, conn)
    found = set()
    with conn.cursor() as cur:
        for _, ref in refs.iterrows():
            query = sql.SQL("SELECT DISTINCT {col} FROM {tbl} WHERE {col} = ANY(%s)").format(
                col=sql.Identifier(ref['column_name']),
                tbl=sql.Identifier(ref['table_name']),
            )
            cur.execute(query, (payment_ids,))
            found.update(row[0] for row in cur.fetchall() if row[0] is not None)
    return found


conn = psycopg2.connect(**PG)
conn.autocommit = False
cur = conn.cursor()

try:
    over = pd.read_csv(OVERPAY_CSV, dtype={'reserve_number': str})
    pay = pd.read_sql_query(
        """
        SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method, COALESCE(notes,'') AS notes
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY reserve_number, payment_date, payment_id
        """,
        conn,
        params=(over['reserve_number'].dropna().tolist(),),
    )

    synthetic = pay[pay['notes'].isin(SYNTHETIC_NOTES)].copy()
    syn_total = synthetic.groupby('reserve_number', dropna=False)['amount'].sum().reset_index(name='synthetic_total')
    merged = over.merge(syn_total, on='reserve_number', how='left').fillna({'synthetic_total': 0})
    merged['variance'] = pd.to_numeric(merged['variance'], errors='coerce').fillna(0).round(2)
    merged['synthetic_total'] = pd.to_numeric(merged['synthetic_total'], errors='coerce').fillna(0).round(2)
    merged['variance_minus_synthetic'] = (merged['variance'] - merged['synthetic_total']).round(2)
    exact = merged[merged['variance_minus_synthetic'].abs() <= 0.01].copy()
    target_reserves = sorted(exact['reserve_number'].dropna().unique().tolist())

    target_rows = synthetic[synthetic['reserve_number'].isin(target_reserves)].copy()
    referenced = find_referenced_payment_ids(conn, target_rows['payment_id'].astype(int).tolist())
    if referenced:
        blocked_reserves = sorted(target_rows[target_rows['payment_id'].isin(referenced)]['reserve_number'].unique().tolist())
    else:
        blocked_reserves = []

    delete_rows = target_rows[~target_rows['payment_id'].isin(referenced)].copy()
    delete_ids = delete_rows['payment_id'].astype(int).tolist()
    delete_reserves = sorted(delete_rows['reserve_number'].unique().tolist())

    if not delete_ids:
        print('No synthetic duplicate rows eligible for deletion.')
        conn.rollback()
    else:
        payment_backup = f'backup_payments_synthetic_cleanup_{TS}'
        cp_backup = f'backup_charter_payments_synthetic_cleanup_{TS}'
        charter_backup = f'backup_charters_synthetic_cleanup_{TS}'

        cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(payment_backup)))
        cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM payments WHERE false').format(sql.Identifier(payment_backup)))
        cur.execute(
            sql.SQL('INSERT INTO {} SELECT * FROM payments WHERE payment_id = ANY(%s)').format(sql.Identifier(payment_backup)),
            (delete_ids,),
        )

        cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(cp_backup)))
        cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM charter_payments WHERE false').format(sql.Identifier(cp_backup)))
        cur.execute(
            sql.SQL("""
                INSERT INTO {}
                SELECT * FROM charter_payments
                WHERE charter_id IN (
                    SELECT charter_id::text FROM charters WHERE reserve_number = ANY(%s)
                )
            """).format(sql.Identifier(cp_backup)),
            (delete_reserves,),
        )

        cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(charter_backup)))
        cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM charters WHERE false').format(sql.Identifier(charter_backup)))
        cur.execute(
            sql.SQL('INSERT INTO {} SELECT * FROM charters WHERE reserve_number = ANY(%s)').format(sql.Identifier(charter_backup)),
            (delete_reserves,),
        )

        cur.execute('DELETE FROM payments WHERE payment_id = ANY(%s)', (delete_ids,))

        cur.execute(
            """
            DELETE FROM charter_payments
            WHERE charter_id IN (
                SELECT charter_id::text FROM charters WHERE reserve_number = ANY(%s)
            )
            """,
            (delete_reserves,),
        )

        cur.execute(
            """
            INSERT INTO charter_payments (
                payment_id, charter_id, amount, payment_date, payment_method, payment_key, source
            )
            SELECT
                p.payment_id,
                c.charter_id::text,
                p.amount,
                p.payment_date,
                p.payment_method,
                p.payment_key,
                'PAYMENTS_TABLE_REBUILD_20260417_AFTER_SYNTHETIC_CLEANUP'
            FROM payments p
            JOIN charters c ON c.reserve_number = p.reserve_number
            WHERE c.reserve_number = ANY(%s)
            """,
            (delete_reserves,),
        )

        cur.execute(
            """
            WITH cp_totals AS (
                SELECT c.charter_id, COALESCE(SUM(cp.amount), 0)::numeric(12,2) AS paid
                FROM charters c
                LEFT JOIN charter_payments cp ON cp.charter_id = c.charter_id::text
                WHERE c.reserve_number = ANY(%s)
                GROUP BY c.charter_id
            )
            UPDATE charters c
            SET amount_paid = t.paid,
                balance_owing = ROUND(COALESCE(c.total_amount_due, 0)::numeric - t.paid, 2),
                balance = ROUND(COALESCE(c.total_amount_due, 0)::numeric - t.paid, 2),
                payment_totals = t.paid
            FROM cp_totals t
            WHERE c.charter_id = t.charter_id
            """,
            (delete_reserves,),
        )

        conn.commit()

        summary = pd.DataFrame([
            ('target_reserves_exact_if_removed', len(target_reserves)),
            ('blocked_referenced_reserves', len(blocked_reserves)),
            ('deleted_payment_rows', len(delete_ids)),
            ('rebuild_reserves', len(delete_reserves)),
        ], columns=['metric','value'])
        summary_path = REPORT_DIR / f'synthetic_cleanup_summary_{TS}.csv'
        summary.to_csv(summary_path, index=False)
        delete_rows.to_csv(REPORT_DIR / f'synthetic_cleanup_deleted_rows_{TS}.csv', index=False)
        if blocked_reserves:
            pd.DataFrame({'reserve_number': blocked_reserves}).to_csv(REPORT_DIR / f'synthetic_cleanup_blocked_reserves_{TS}.csv', index=False)

        print(f'payment_backup={payment_backup}')
        print(f'charter_backup={charter_backup}')
        print(f'charter_payments_backup={cp_backup}')
        print(summary.to_string(index=False))
        print(f'summary_report={summary_path}')
        if blocked_reserves:
            print('blocked_reserves_sample=' + ','.join(blocked_reserves[:30]))
finally:
    cur.close()
    conn.close()

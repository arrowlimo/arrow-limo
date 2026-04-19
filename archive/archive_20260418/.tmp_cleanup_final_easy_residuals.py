import pandas as pd
import psycopg2
from psycopg2 import sql
from datetime import datetime
from pathlib import Path

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
OVERPAY_CSV = r"L:\limo\reports\overpaid_analysis_2012_2017_20260417_215459.csv"
REPORT_DIR = Path(r"L:\limo\reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

TARGET_SYNC_DELETE = {
    '005410', '005684', '006098', '006232', '006336', '006490', '007255'
}

conn = psycopg2.connect(**PG)
conn.autocommit = False
cur = conn.cursor()

try:
    over = pd.read_csv(OVERPAY_CSV, dtype={'reserve_number': str})
    target_reserves = sorted(set(TARGET_SYNC_DELETE) | {'012391'})
    pay = pd.read_sql_query(
        """
        SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method, COALESCE(notes,'') AS notes
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY reserve_number, payment_date, payment_id
        """,
        conn,
        params=(target_reserves,),
    )

    delete_df = pay[
        ((pay['reserve_number'].isin(TARGET_SYNC_DELETE)) & (pay['notes'] == 'Inserted from LMS2026d payment sync'))
        | ((pay['reserve_number'] == '012391') & (pay['notes'] == 'Backfilled from charter_payments') & (pd.to_datetime(pay['payment_date'], errors='coerce').dt.year == 2025))
    ].copy()

    delete_ids = delete_df['payment_id'].astype(int).tolist()
    touched_reserves = sorted(delete_df['reserve_number'].unique().tolist())

    if not delete_ids:
        print('No final easy residual rows to delete.')
        conn.rollback()
    else:
        payment_backup = f'backup_payments_final_easy_residuals_{TS}'
        charter_backup = f'backup_charters_final_easy_residuals_{TS}'
        cp_backup = f'backup_charter_payments_final_easy_residuals_{TS}'

        cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(payment_backup)))
        cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM payments WHERE false').format(sql.Identifier(payment_backup)))
        cur.execute(sql.SQL('INSERT INTO {} SELECT * FROM payments WHERE payment_id = ANY(%s)').format(sql.Identifier(payment_backup)), (delete_ids,))

        cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(charter_backup)))
        cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM charters WHERE false').format(sql.Identifier(charter_backup)))
        cur.execute(sql.SQL('INSERT INTO {} SELECT * FROM charters WHERE reserve_number = ANY(%s)').format(sql.Identifier(charter_backup)), (touched_reserves,))

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
            (touched_reserves,),
        )

        cur.execute('DELETE FROM payments WHERE payment_id = ANY(%s)', (delete_ids,))
        cur.execute(
            """
            DELETE FROM charter_payments
            WHERE charter_id IN (
                SELECT charter_id::text FROM charters WHERE reserve_number = ANY(%s)
            )
            """,
            (touched_reserves,),
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
                'PAYMENTS_TABLE_REBUILD_20260417_AFTER_FINAL_EASY_RESIDUALS'
            FROM payments p
            JOIN charters c ON c.reserve_number = p.reserve_number
            WHERE c.reserve_number = ANY(%s)
            """,
            (touched_reserves,),
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
            (touched_reserves,),
        )

        conn.commit()
        summary = pd.DataFrame([
            ('deleted_payment_rows', len(delete_ids)),
            ('touched_reserves', len(touched_reserves)),
        ], columns=['metric','value'])
        summary_path = REPORT_DIR / f'final_easy_residual_cleanup_summary_{TS}.csv'
        summary.to_csv(summary_path, index=False)
        delete_df.to_csv(REPORT_DIR / f'final_easy_residual_cleanup_deleted_rows_{TS}.csv', index=False)
        print(f'payment_backup={payment_backup}')
        print(f'charter_backup={charter_backup}')
        print(f'charter_payments_backup={cp_backup}')
        print(summary.to_string(index=False))
        print(f'summary_report={summary_path}')
finally:
    cur.close()
    conn.close()

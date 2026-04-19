import pandas as pd
import psycopg2
from psycopg2 import sql
from datetime import datetime
from pathlib import Path

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
BUCKET_CSV = r"L:\limo\reports\final_residual_overpay_buckets_20260417_214440.csv"
REPORT_DIR = Path(r"L:\limo\reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")


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
    buckets = pd.read_csv(BUCKET_CSV, dtype={'reserve_number': str})
    phase2_reserves = buckets[buckets['category'].isin([
        'screenshot_reconcile_duplicate',
        'two_synthetic_sources_overlap',
        'backfill_plus_sync_overlap',
    ])]['reserve_number'].dropna().tolist()

    pay = pd.read_sql_query(
        """
        SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method, COALESCE(notes,'') AS notes
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY reserve_number, payment_date, payment_id
        """,
        conn,
        params=(phase2_reserves,),
    )

    delete_ids = []
    delete_reason_rows = []

    screenshot_reserves = buckets[buckets['category'] == 'screenshot_reconcile_duplicate']['reserve_number'].dropna().tolist()
    screenshot_rows = pay[(pay['reserve_number'].isin(screenshot_reserves)) & (pay['notes'] == 'LMS screenshot reconcile 2026-02-25 (missing payment line)')]
    for _, row in screenshot_rows.iterrows():
        delete_ids.append(int(row['payment_id']))
        delete_reason_rows.append({'reserve_number': row['reserve_number'], 'payment_id': int(row['payment_id']), 'notes': row['notes'], 'amount': row['amount'], 'reason': 'delete_screenshot_duplicate'})

    synthetic_reserves = buckets[buckets['category'].isin(['two_synthetic_sources_overlap', 'backfill_plus_sync_overlap'])]['reserve_number'].dropna().tolist()
    gapfill_rows = pay[(pay['reserve_number'].isin(synthetic_reserves)) & (pay['notes'] == 'LMS-verified balancing payment - 2012 import gap')]
    for _, row in gapfill_rows.iterrows():
        delete_ids.append(int(row['payment_id']))
        delete_reason_rows.append({'reserve_number': row['reserve_number'], 'payment_id': int(row['payment_id']), 'notes': row['notes'], 'amount': row['amount'], 'reason': 'delete_gapfill_overlap'})

    # Special-case 012194: remove the 2025 overlay backfill rows, keep the dated 2016/source rows.
    rows_012194 = pay[(pay['reserve_number'] == '012194') & (pay['notes'] == 'Backfilled from charter_payments') & (pd.to_datetime(pay['payment_date'], errors='coerce').dt.year == 2025)]
    for _, row in rows_012194.iterrows():
        delete_ids.append(int(row['payment_id']))
        delete_reason_rows.append({'reserve_number': row['reserve_number'], 'payment_id': int(row['payment_id']), 'notes': row['notes'], 'amount': row['amount'], 'reason': 'delete_2025_backfill_overlay'})

    delete_ids = sorted(set(delete_ids))
    if not delete_ids:
        print('No phase2 residual cleanup rows selected.')
        conn.rollback()
    else:
        referenced = find_referenced_payment_ids(conn, delete_ids)
        eligible_ids = [payment_id for payment_id in delete_ids if payment_id not in referenced]
        blocked_ids = sorted(set(delete_ids) - set(eligible_ids))

        delete_df = pd.DataFrame(delete_reason_rows)
        delete_df = delete_df[delete_df['payment_id'].isin(eligible_ids)].copy()
        touched_reserves = sorted(delete_df['reserve_number'].unique().tolist()) if not delete_df.empty else []

        if not eligible_ids:
            print('No eligible phase2 rows after FK filtering.')
            if blocked_ids:
                print('blocked_ids=' + ','.join(str(x) for x in blocked_ids[:50]))
            conn.rollback()
        else:
            payment_backup = f'backup_payments_residual_phase2_{TS}'
            charter_backup = f'backup_charters_residual_phase2_{TS}'
            cp_backup = f'backup_charter_payments_residual_phase2_{TS}'

            cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(payment_backup)))
            cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM payments WHERE false').format(sql.Identifier(payment_backup)))
            cur.execute(sql.SQL('INSERT INTO {} SELECT * FROM payments WHERE payment_id = ANY(%s)').format(sql.Identifier(payment_backup)), (eligible_ids,))

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

            cur.execute('DELETE FROM payments WHERE payment_id = ANY(%s)', (eligible_ids,))
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
                    'PAYMENTS_TABLE_REBUILD_20260417_AFTER_PHASE2_CLEANUP'
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
                ('eligible_deletes', len(eligible_ids)),
                ('blocked_deletes', len(blocked_ids)),
                ('touched_reserves', len(touched_reserves)),
            ], columns=['metric','value'])
            summary_path = REPORT_DIR / f'residual_phase2_cleanup_summary_{TS}.csv'
            summary.to_csv(summary_path, index=False)
            delete_df.to_csv(REPORT_DIR / f'residual_phase2_cleanup_deleted_rows_{TS}.csv', index=False)
            if blocked_ids:
                pd.DataFrame({'payment_id': blocked_ids}).to_csv(REPORT_DIR / f'residual_phase2_cleanup_blocked_payment_ids_{TS}.csv', index=False)

            print(f'payment_backup={payment_backup}')
            print(f'charter_backup={charter_backup}')
            print(f'charter_payments_backup={cp_backup}')
            print(summary.to_string(index=False))
            print(f'summary_report={summary_path}')
            if blocked_ids:
                print('blocked_ids=' + ','.join(str(x) for x in blocked_ids[:50]))
finally:
    cur.close()
    conn.close()

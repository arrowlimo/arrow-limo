import psycopg2
from psycopg2 import sql
from datetime import datetime

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
TS = datetime.now().strftime('%Y%m%d_%H%M%S')
RESERVE = '006318'
DELETE_PAYMENT_ID = 45659

conn = psycopg2.connect(**PG)
conn.autocommit = False
cur = conn.cursor()

try:
    payment_backup = f'backup_payments_fix_006318_{TS}'
    charter_backup = f'backup_charters_fix_006318_{TS}'
    cp_backup = f'backup_charter_payments_fix_006318_{TS}'

    cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(payment_backup)))
    cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM payments WHERE false').format(sql.Identifier(payment_backup)))
    cur.execute(sql.SQL('INSERT INTO {} SELECT * FROM payments WHERE payment_id = %s').format(sql.Identifier(payment_backup)), (DELETE_PAYMENT_ID,))

    cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(charter_backup)))
    cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM charters WHERE false').format(sql.Identifier(charter_backup)))
    cur.execute(sql.SQL('INSERT INTO {} SELECT * FROM charters WHERE reserve_number = %s').format(sql.Identifier(charter_backup)), (RESERVE,))

    cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(cp_backup)))
    cur.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM charter_payments WHERE false').format(sql.Identifier(cp_backup)))
    cur.execute(
        sql.SQL("""
            INSERT INTO {}
            SELECT * FROM charter_payments
            WHERE charter_id IN (
                SELECT charter_id::text FROM charters WHERE reserve_number = %s
            )
        """).format(sql.Identifier(cp_backup)),
        (RESERVE,),
    )

    cur.execute('DELETE FROM payments WHERE payment_id = %s', (DELETE_PAYMENT_ID,))
    cur.execute(
        """
        DELETE FROM charter_payments
        WHERE charter_id IN (
            SELECT charter_id::text FROM charters WHERE reserve_number = %s
        )
        """,
        (RESERVE,),
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
            'PAYMENTS_TABLE_REBUILD_20260417_AFTER_006318_FIX'
        FROM payments p
        JOIN charters c ON c.reserve_number = p.reserve_number
        WHERE c.reserve_number = %s
        """,
        (RESERVE,),
    )
    cur.execute(
        """
        WITH cp_totals AS (
            SELECT c.charter_id, COALESCE(SUM(cp.amount), 0)::numeric(12,2) AS paid
            FROM charters c
            LEFT JOIN charter_payments cp ON cp.charter_id = c.charter_id::text
            WHERE c.reserve_number = %s
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
        (RESERVE,),
    )

    conn.commit()
    print(f'payment_backup={payment_backup}')
    print(f'charter_backup={charter_backup}')
    print(f'charter_payments_backup={cp_backup}')
    print('deleted_payment_id=45659')
except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()

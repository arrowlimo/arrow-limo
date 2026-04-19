import psycopg2
import pandas as pd

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')

# Target keys from LMS verification
K_6274 = '0006274'  # +385.00 for 006504
K_6281 = '0006281'  # -384.99 for 006504
K_6375 = '0006375'  # belongs to 006555 in LMS, not 006504

conn = psycopg2.connect(**PG)
conn.autocommit = False
cur = conn.cursor()

try:
    # Show pre-state
    pre_sql = """
        SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method
        FROM payments
        WHERE payment_key IN (%s, %s, %s)
        ORDER BY payment_key, payment_id
    """
    pre_df = pd.read_sql_query(pre_sql, conn, params=[K_6274, K_6281, K_6375])
    print('PRE payments rows for key set:')
    print(pre_df.to_string(index=False) if not pre_df.empty else '<none>')

    # Backup rows we will touch
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_payments_key_repair_20260417 AS
        SELECT * FROM payments WHERE false
        """
    )
    cur.execute(
        """
        INSERT INTO backup_payments_key_repair_20260417
        SELECT * FROM payments
        WHERE payment_key IN (%s, %s, %s)
           OR reserve_number IN ('006504', '006555')
        """,
        (K_6274, K_6281, K_6375),
    )

    # Get a template row for insert defaults (any existing row)
    cur.execute(
        """
        SELECT payment_method
        FROM payments
        WHERE payment_key = %s
        ORDER BY payment_id DESC
        LIMIT 1
        """,
        (K_6375,),
    )
    t = cur.fetchone()
    template_method = t[0] if t and t[0] else 'unknown'

    # Correct key 0006375 to its LMS reserve/amount/date
    cur.execute(
        """
        UPDATE payments
        SET reserve_number = '006555',
            payment_date = DATE '2012-08-03',
            amount = 175.00,
            payment_method = COALESCE(payment_method, %s)
        WHERE payment_key = %s
        """,
        (template_method, K_6375),
    )

    # Upsert key 0006274 (+385.00) for reserve 006504
    cur.execute(
        """
        UPDATE payments
        SET reserve_number = '006504',
            payment_date = DATE '2012-07-20',
            amount = 385.00,
            payment_method = COALESCE(payment_method, %s)
        WHERE payment_key = %s
        """,
        (template_method, K_6274),
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO payments (reserve_number, amount, payment_date, payment_method, payment_key)
            VALUES ('006504', 385.00, DATE '2012-07-20', %s, %s)
            """,
            (template_method, K_6274),
        )

    # Upsert key 0006281 (-384.99) for reserve 006504
    cur.execute(
        """
        UPDATE payments
        SET reserve_number = '006504',
            payment_date = DATE '2012-07-20',
            amount = -384.99,
            payment_method = COALESCE(payment_method, %s)
        WHERE payment_key = %s
        """,
        (template_method, K_6281),
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO payments (reserve_number, amount, payment_date, payment_method, payment_key)
            VALUES ('006504', -384.99, DATE '2012-07-20', %s, %s)
            """,
            (template_method, K_6281),
        )

    # Rebuild charter_payments rows for affected reserves from payments table
    # Affected reserves: 006504 and 006555
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_charter_payments_key_repair_20260417 AS
        SELECT * FROM charter_payments WHERE false
        """
    )
    cur.execute(
        """
        INSERT INTO backup_charter_payments_key_repair_20260417
        SELECT cp.*
        FROM charter_payments cp
        JOIN charters c ON cp.charter_id = c.charter_id::text
        WHERE c.reserve_number IN ('006504', '006555')
        """
    )

    cur.execute(
        """
        DELETE FROM charter_payments cp
        USING charters c
        WHERE cp.charter_id = c.charter_id::text
          AND c.reserve_number IN ('006504', '006555')
        """
    )

    cur.execute(
        """
        INSERT INTO charter_payments (
            charter_id, amount, payment_date, payment_method, payment_key, source, payment_id
        )
        SELECT
            c.charter_id::text,
            p.amount,
            p.payment_date,
            p.payment_method,
            p.payment_key,
            'PAYMENTS_TABLE_REBUILD_20260417_KEY_REPAIR',
            p.payment_id
        FROM payments p
        JOIN charters c ON c.reserve_number = p.reserve_number
        WHERE c.reserve_number IN ('006504', '006555')
        """
    )

    # Re-sync headers for affected reserves
    cur.execute(
        """
        WITH cp_totals AS (
            SELECT c.charter_id, COALESCE(SUM(cp.amount), 0)::numeric(12,2) AS paid
            FROM charters c
            LEFT JOIN charter_payments cp ON cp.charter_id = c.charter_id::text
            WHERE c.reserve_number IN ('006504', '006555')
            GROUP BY c.charter_id
        )
        UPDATE charters c
        SET amount_paid = t.paid,
            balance_owing = ROUND(COALESCE(c.total_amount_due,0)::numeric - t.paid, 2),
            balance = ROUND(COALESCE(c.total_amount_due,0)::numeric - t.paid, 2),
            payment_totals = t.paid
        FROM cp_totals t
        WHERE c.charter_id = t.charter_id
        """
    )

    conn.commit()

    post_df = pd.read_sql_query(pre_sql, conn, params=[K_6274, K_6281, K_6375])
    print('\nPOST payments rows for key set:')
    print(post_df.to_string(index=False) if not post_df.empty else '<none>')

    chk = pd.read_sql_query(
        """
        SELECT c.reserve_number, c.total_amount_due, c.amount_paid, c.balance_owing,
               COALESCE(SUM(cp.amount),0) AS cp_sum
        FROM charters c
        LEFT JOIN charter_payments cp ON cp.charter_id = c.charter_id::text
        WHERE c.reserve_number IN ('006504','006555','006341')
        GROUP BY c.reserve_number, c.total_amount_due, c.amount_paid, c.balance_owing
        ORDER BY c.reserve_number
        """,
        conn,
    )
    print('\nPOST charter summary (006341/006504/006555):')
    print(chk.to_string(index=False))

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()

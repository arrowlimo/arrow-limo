import pandas as pd
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')

cols = pd.read_sql_query(
    """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='income_ledger'
    ORDER BY ordinal_position
    """,
    conn,
)
print('INCOME_LEDGER_COLUMNS')
print(cols.to_string(index=False))

ids = [8029, 8056, 7988]
rows = pd.read_sql_query(
    """
    SELECT *
    FROM income_ledger
    WHERE payment_id = ANY(%s)
    ORDER BY payment_id, income_id
    """,
    conn,
    params=(ids,),
)
print('\nINCOME_LEDGER_TARGET_ROWS')
print(rows.to_string(index=False))

for reserve in ['006341', '006311', '007504']:
    pay = pd.read_sql_query(
        """
        SELECT payment_id, reserve_number, charter_id, payment_key, payment_date, amount, payment_method, COALESCE(notes,'') AS notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
        """,
        conn,
        params=(reserve,),
    )
    inc = pd.read_sql_query(
        """
        SELECT income_id, payment_id, charter_id, reserve_number, transaction_date, amount, payment_method, payment_reference, description, notes
        FROM income_ledger
        WHERE reserve_number = %s
        ORDER BY transaction_date, income_id
        """,
        conn,
        params=(reserve,),
    )
    print(f'\nRESERVE {reserve} PAYMENTS')
    print(pay.to_string(index=False))
    print(f'\nRESERVE {reserve} INCOME_LEDGER')
    print(inc.to_string(index=False))

conn.close()

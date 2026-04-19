import pandas as pd
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
keys = ['0007208', '0007248', '0007454']
df = pd.read_sql_query(
    """
    SELECT payment_id, reserve_number, charter_id, payment_key, payment_date, amount, payment_method, COALESCE(notes,'') AS notes
    FROM payments
    WHERE payment_key = ANY(%s)
    ORDER BY payment_key, payment_id
    """,
    conn,
    params=(keys,),
)
conn.close()
print(df.to_string(index=False))

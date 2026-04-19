import pandas as pd
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
df = pd.read_sql_query(
    """
    SELECT column_name, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='income_ledger'
      AND column_name='payment_id'
    """,
    conn,
)
conn.close()
print(df.to_string(index=False))

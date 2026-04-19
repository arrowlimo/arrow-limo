import pandas as pd
import psycopg2

OVERPAY_CSV = r"L:\limo\reports\overpaid_analysis_2012_2017_20260417_214440.csv"
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
over = pd.read_csv(OVERPAY_CSV, dtype={'reserve_number': str})
q = """
SELECT reserve_number, COALESCE(notes, '') AS notes, COUNT(*) AS rows, SUM(amount) AS amount
FROM payments
WHERE reserve_number = ANY(%s)
GROUP BY reserve_number, COALESCE(notes, '')
ORDER BY reserve_number, amount DESC
"""
df = pd.read_sql_query(q, conn, params=(over['reserve_number'].dropna().tolist(),))
conn.close()
print(df.to_string(index=False))

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
cur = conn.cursor()

cur.execute(
    """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='banking_transactions'
    ORDER BY ordinal_position
    """
)
print("BANKING_COLUMNS")
for col, dtype in cur.fetchall():
    print(f"{col}|{dtype}")

cur.execute(
    """
    SELECT reconciliation_status, COUNT(1), COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE reconciliation_status = 'CASH_BOX_REVIEW'
    GROUP BY reconciliation_status
    """
)
print("CASH_BOX_REVIEW_SUMMARY")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()

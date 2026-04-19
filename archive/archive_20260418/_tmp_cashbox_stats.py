import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
cur = conn.cursor()

print("TRANSFER_STATUS_BREAKDOWN")
cur.execute(
    """
    SELECT COALESCE(is_transfer::text, 'NULL') AS transfer_flag,
           COUNT(1),
           COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE reconciliation_status='CASH_BOX_REVIEW'
    GROUP BY COALESCE(is_transfer::text, 'NULL')
    ORDER BY COUNT(1) DESC
    """
)
for row in cur.fetchall():
    print("|".join(str(x) for x in row))

print("TOP_CATEGORIES")
cur.execute(
    """
    SELECT COALESCE(category,'NULL') AS category,
           COUNT(1),
           COALESCE(SUM(debit_amount),0)
    FROM banking_transactions
    WHERE reconciliation_status='CASH_BOX_REVIEW'
    GROUP BY COALESCE(category,'NULL')
    ORDER BY COUNT(1) DESC, COALESCE(SUM(debit_amount),0) DESC
    LIMIT 20
    """
)
for row in cur.fetchall():
    print("|".join(str(x) for x in row))

print("SAMPLE_ALREADY_TRANSFER")
cur.execute(
    """
    SELECT transaction_id, transaction_date, debit_amount, description
    FROM banking_transactions
    WHERE reconciliation_status='CASH_BOX_REVIEW'
      AND is_transfer IS TRUE
    ORDER BY debit_amount DESC, transaction_id
    LIMIT 10
    """
)
for row in cur.fetchall():
    print("|".join(str(x) for x in row))

cur.close()
conn.close()

import os
import psycopg2

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

with psycopg2.connect(**DSN) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(debit_amount),0)
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date)=%s
              AND (
                  description ILIKE %s
                  OR description ILIKE %s
                  OR description ILIKE %s
                  OR description ILIKE %s
                  OR description ILIKE %s
              )
            """,
            (2012, "%receiver general%", "%canada revenue%", "%revenue canada%", "%cra%", "%gst%"),
        )
        print(cur.fetchone())

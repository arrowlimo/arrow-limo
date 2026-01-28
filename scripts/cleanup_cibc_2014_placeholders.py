import os
import psycopg2

ACCOUNT = '0228362'

DELETES = [
    # (date, amount)
    ('2014-01-31', 115.42),
    ('2014-02-28', 61.15),
    ('2014-02-28', 1.00),
    ('2014-03-31', 119.39),
    ('2014-04-30', 177.00),
    ('2014-04-30', 110.51),
    ('2014-05-31', 115.07),
]

def main():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    conn = psycopg2.connect(host=host, dbname=name, user=user, password=password)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS banking_transactions_cibc_2014_backup_cleanup AS
        SELECT * FROM banking_transactions
        WHERE account_number = %s AND EXTRACT(YEAR FROM transaction_date) = 2014
    """, (ACCOUNT,))
    print("Backup created for cleanup: banking_transactions_cibc_2014_backup_cleanup")

    total = 0
    for dt, amt in DELETES:
        cur.execute(
            """
                        DELETE FROM banking_transactions
                        WHERE account_number = %s
                            AND transaction_date = %s
                            AND description ILIKE %s
                            AND COALESCE(debit_amount,0) = %s
            RETURNING transaction_id
            """,
                        (ACCOUNT, dt, 'Cheque%', amt)
        )
        rows = cur.fetchall()
        if rows:
            print(f"Deleted {len(rows)} rows for {dt} amount {amt}")
            total += len(rows)

    conn.commit()
    print(f"Cleanup complete. Deleted {total} rows.")
    conn.close()

if __name__ == '__main__':
    main()

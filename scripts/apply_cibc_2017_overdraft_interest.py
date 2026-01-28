import argparse
import os
import psycopg2
from datetime import date

ACCOUNT = '0228362'

INTEREST_ROWS = [
    (date(2017, 1, 31), 'OVERDRAFT INTEREST', 114.23),
    (date(2017, 2, 28), 'OVERDRAFT INTEREST', 105.02),
    (date(2017, 3, 31), 'OVERDRAFT INTEREST', 118.14),
    (date(2017, 4, 28), 'OVERDRAFT INTEREST', 116.37),
    (date(2017, 5, 31), 'OVERDRAFT INTEREST', 122.32),
    (date(2017, 6, 30), 'OVERDRAFT INTEREST', 120.49),
    (date(2017, 7, 31), 'OVERDRAFT INTEREST', 126.65),
    (date(2017, 8, 31), 'OVERDRAFT INTEREST', 128.91),
    (date(2017, 9, 29), 'OVERDRAFT INTEREST', 126.98),
    (date(2017, 10, 31), 'OVERDRAFT INTEREST', 133.53),
    (date(2017, 11, 30), 'OVERDRAFT INTEREST', 131.54),
    (date(2017, 12, 29), 'OVERDRAFT INTEREST', 138.27),
]

SERVICE_ROWS = [
    (date(2017, 10, 6), 'SERVICE CHARGE', 3.50),
]


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def upsert_rows(cur, rows):
    planned = []
    existing = []
    for d, desc, amt in rows:
        cur.execute(
            """
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = %s AND transaction_date = %s
              AND description ILIKE %s
              AND COALESCE(debit_amount,0) = %s
            """,
            (ACCOUNT, d, desc + '%', amt)
        )
        row = cur.fetchone()
        if row:
            existing.append((d, amt, desc))
        else:
            planned.append((d, desc, amt))
    return planned, existing


def main():
    parser = argparse.ArgumentParser(description='Apply CIBC 2017 overdraft interest + service charge rows')
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    planned_i, existing_i = upsert_rows(cur, INTEREST_ROWS)
    planned_s, existing_s = upsert_rows(cur, SERVICE_ROWS)

    print(f"Existing interest rows: {len(existing_i)}")
    print(f"Planned interest inserts: {len(planned_i)}")
    for d, desc, amt in planned_i:
        print(f"  {d} — {amt:.2f} {desc}")

    print(f"Existing service rows: {len(existing_s)}")
    print(f"Planned service inserts: {len(planned_s)}")
    for d, desc, amt in planned_s:
        print(f"  {d} — {amt:.2f} {desc}")

    if args.write:
        inserted = 0
        for d, desc, amt in planned_i + planned_s:
            cur.execute(
                """
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount
                )
                SELECT %s, %s, %s, %s, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM banking_transactions bt
                    WHERE bt.account_number = %s AND bt.transaction_date = %s
                      AND bt.description ILIKE %s
                      AND COALESCE(bt.debit_amount,0) = %s
                )
                """,
                (ACCOUNT, d, desc, amt, ACCOUNT, d, desc + '%', amt)
            )
            inserted += cur.rowcount
        conn.commit()
        print(f"Inserted {inserted} rows.")
    else:
        print("Dry-run complete. Use --write to apply.")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()

import argparse
import os
import psycopg2
from datetime import date

INTEREST_ROWS = [
    (date(2016, 1, 29), 'OVERDRAFT INTEREST', 92.71),
    (date(2016, 2, 29), 'OVERDRAFT INTEREST', 88.27),
    (date(2016, 3, 31), 'OVERDRAFT INTEREST', 95.94),
    (date(2016, 4, 30), 'OVERDRAFT INTEREST', 94.50),
    (date(2016, 5, 31), 'OVERDRAFT INTEREST', 99.33),
    (date(2016, 6, 30), 'OVERDRAFT INTEREST', 97.84),
    (date(2016, 7, 29), 'OVERDRAFT INTEREST', 102.85),
    (date(2016, 8, 31), 'OVERDRAFT INTEREST', 104.68),
    (date(2016, 9, 30), 'OVERDRAFT INTEREST', 103.11),
    (date(2016, 10, 31), 'OVERDRAFT INTEREST', 108.39),
    (date(2016, 11, 30), 'OVERDRAFT INTEREST', 106.77),
    (date(2016, 12, 30), 'OVERDRAFT INTEREST', 112.23),
]

ACCOUNT = '0228362'


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def main():
    parser = argparse.ArgumentParser(description='Apply CIBC 2016 overdraft interest rows')
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    planned = []
    existing = []

    for d, desc, amt in INTEREST_ROWS:
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
            existing.append((d, amt))
        else:
            planned.append((d, desc, amt))

    print(f"Existing rows found: {len(existing)}")
    for d, amt in existing:
        print(f"  {d} — {amt:.2f} (exists)")

    print(f"Planned inserts: {len(planned)}")
    for d, desc, amt in planned:
        print(f"  {d} — {amt:.2f} {desc}")

    if args.write and planned:
        inserted = 0
        for d, desc, amt in planned:
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

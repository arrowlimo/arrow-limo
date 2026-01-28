import argparse
import os
import psycopg2
from datetime import date

INTEREST_ROWS = [
    (date(2015, 1, 30), 'OVERDRAFT INTEREST', 75.29),
    (date(2015, 2, 27), 'OVERDRAFT INTEREST', 69.21),
    (date(2015, 3, 31), 'OVERDRAFT INTEREST', 77.86),
    (date(2015, 4, 30), 'OVERDRAFT INTEREST', 76.69),
    (date(2015, 5, 29), 'OVERDRAFT INTEREST', 80.62),
    (date(2015, 6, 30), 'OVERDRAFT INTEREST', 79.41),
    (date(2015, 7, 31), 'OVERDRAFT INTEREST', 83.47),
    (date(2015, 8, 31), 'OVERDRAFT INTEREST', 84.96),
    (date(2015, 9, 30), 'OVERDRAFT INTEREST', 83.69),
    (date(2015, 10, 30), 'OVERDRAFT INTEREST', 87.97),
    (date(2015, 11, 30), 'OVERDRAFT INTEREST', 86.65),
    (date(2015, 12, 31), 'OVERDRAFT INTEREST', 91.08),
]

ACCOUNT = '0228362'


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def main():
    parser = argparse.ArgumentParser(description='Apply CIBC 2015 overdraft interest rows')
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
        # Optional: no mass backup; these are targeted inserts.
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

import argparse
import os
import psycopg2
from datetime import date

ACCOUNT = '0228362'
OPENING = -4221.09
TARGETS = [
    (date(2015, 1, 31), -4296.38),
    (date(2015, 2, 28), -4365.59),
    (date(2015, 3, 31), -4443.45),
    (date(2015, 4, 30), -4520.14),
    (date(2015, 5, 31), -4600.76),
    (date(2015, 6, 30), -4680.17),
    (date(2015, 7, 31), -4763.64),
    (date(2015, 8, 31), -4848.60),
    (date(2015, 9, 30), -4932.29),
    (date(2015, 10, 31), -5020.26),
    (date(2015, 11, 30), -5106.91),
    (date(2015, 12, 31), -5197.99),
]

INTEREST = {
    date(2015, 1, 30): 75.29,
    date(2015, 2, 27): 69.21,
    date(2015, 3, 31): 77.86,
    date(2015, 4, 30): 76.69,
    date(2015, 5, 29): 80.62,
    date(2015, 6, 30): 79.41,
    date(2015, 7, 31): 83.47,
    date(2015, 8, 31): 84.96,
    date(2015, 9, 30): 83.69,
    date(2015, 10, 30): 87.97,
    date(2015, 11, 30): 86.65,
    date(2015, 12, 31): 91.08,
}


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def main():
    parser = argparse.ArgumentParser(description='Reconcile 2015 CIBC balances using interest-only model')
    parser.add_argument('--write', action='store_true', help='Apply balance updates to interest rows')
    args = parser.parse_args()

    # Verify chain
    running = OPENING
    chain_ok = True
    for month_end, target in TARGETS:
        # find interest on/before this month-end
        # choose the exact interest date in this month
        interest_dates = [d for d in INTEREST.keys() if d.month == month_end.month]
        if len(interest_dates) != 1:
            print(f"Error: expected 1 interest date for {month_end}, found {interest_dates}")
            chain_ok = False
            continue
        d = interest_dates[0]
        running = round(running - INTEREST[d], 2)
        ok = abs(running - target) < 0.01
        print(f"{month_end} — opening {running + INTEREST[d]:.2f} - interest {INTEREST[d]:.2f} = {running:.2f} | target {target:.2f} | {'OK' if ok else 'MISMATCH'}")
        if not ok:
            chain_ok = False

    if not chain_ok:
        print("Chain mismatch detected; aborting write.")
        return

    conn = get_conn()
    cur = conn.cursor()

    # Update the balance column for each interest transaction to the month-end target
    # We set the interest transaction's balance equal to the corresponding month-end balance.
    updates = 0
    for month_end, target in TARGETS:
        interest_date = [d for d in INTEREST.keys() if d.month == month_end.month][0]
        interest_amt = INTEREST[interest_date]
        # Update matching interest row
        cur.execute(
            """
            UPDATE banking_transactions
            SET balance = %s
            WHERE account_number = %s AND transaction_date = %s
              AND description ILIKE %s
              AND COALESCE(debit_amount,0) = %s
            """,
            (target, ACCOUNT, interest_date, 'OVERDRAFT INTEREST%', interest_amt)
        )
        updates += cur.rowcount
    if args.write:
        conn.commit()
        print(f"Applied {updates} balance updates.")
    else:
        conn.rollback()
        print(f"Dry-run: would apply {updates} balance updates.")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()

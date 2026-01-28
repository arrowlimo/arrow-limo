import argparse
import os
import psycopg2
from datetime import date

ACCOUNT = '0228362'
OPENING = -5197.99
TARGETS = [
    (date(2016, 1, 31), -5290.70),
    (date(2016, 2, 29), -5378.97),
    (date(2016, 3, 31), -5474.91),
    (date(2016, 4, 30), -5569.41),
    (date(2016, 5, 31), -5668.74),
    (date(2016, 6, 30), -5766.58),
    (date(2016, 7, 31), -5869.43),
    (date(2016, 8, 31), -5974.11),
    (date(2016, 9, 30), -6077.22),
    (date(2016, 10, 31), -6185.61),
    (date(2016, 11, 30), -6292.38),
    (date(2016, 12, 31), -6404.61),
]

INTEREST = {
    date(2016, 1, 29): 92.71,
    date(2016, 2, 29): 88.27,
    date(2016, 3, 31): 95.94,
    date(2016, 4, 30): 94.50,
    date(2016, 5, 31): 99.33,
    date(2016, 6, 30): 97.84,
    date(2016, 7, 29): 102.85,
    date(2016, 8, 31): 104.68,
    date(2016, 9, 30): 103.11,
    date(2016, 10, 31): 108.39,
    date(2016, 11, 30): 106.77,
    date(2016, 12, 30): 112.23,
}


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def main():
    parser = argparse.ArgumentParser(description='Reconcile 2016 CIBC balances using interest-only model')
    parser.add_argument('--write', action='store_true', help='Apply balance updates to interest rows')
    args = parser.parse_args()

    # Verify chain (note April is skipped)
    running = OPENING
    chain_ok = True
    prev_month = 0
    for month_end, target in TARGETS:
        # Check if we skipped a month
        if prev_month > 0 and month_end.month != prev_month + 1 and not (prev_month == 12):
            print(f"Warning: Gap detected between month {prev_month} and {month_end.month}")
        prev_month = month_end.month
        
        # find interest on/before this month-end
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
    updates = 0
    for month_end, target in TARGETS:
        interest_date = [d for d in INTEREST.keys() if d.month == month_end.month][0]
        interest_amt = INTEREST[interest_date]
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

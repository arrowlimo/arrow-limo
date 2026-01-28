import argparse
import os
import psycopg2
from datetime import date

ACCOUNT = '0228362'
OPENING = -6404.61
TARGETS = [
    (date(2017, 1, 31), -6518.84),
    (date(2017, 2, 28), -6623.86),
    (date(2017, 3, 31), -6742.00),
    (date(2017, 4, 28), -6858.37),
    (date(2017, 5, 31), -6980.69),
    (date(2017, 6, 30), -7101.18),
    (date(2017, 7, 31), -7227.83),
    (date(2017, 8, 31), -7356.74),
    (date(2017, 9, 29), -7483.72),
    (date(2017, 10, 31), -7620.75),
    (date(2017, 11, 30), -7752.29),
    (date(2017, 12, 29), -7890.56),
]

INTEREST = {
    date(2017, 1, 31): 114.23,
    date(2017, 2, 28): 105.02,
    date(2017, 3, 31): 118.14,
    date(2017, 4, 28): 116.37,
    date(2017, 5, 31): 122.32,
    date(2017, 6, 30): 120.49,
    date(2017, 7, 31): 126.65,
    date(2017, 8, 31): 128.91,
    date(2017, 9, 29): 126.98,
    date(2017, 10, 31): 133.53,
    date(2017, 11, 30): 131.54,
    date(2017, 12, 29): 138.27,
}

SERVICE = {
    date(2017, 10, 6): 3.50,
}


def get_conn():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def main():
    parser = argparse.ArgumentParser(description='Reconcile 2017 CIBC balances using interest + service charges')
    parser.add_argument('--write', action='store_true', help='Apply balance updates to interest/service rows')
    args = parser.parse_args()

    running = OPENING
    chain_ok = True
    for month_end, target in TARGETS:
        # Apply any service charges within the month before interest
        service_dates = [d for d in SERVICE.keys() if d.month == month_end.month]
        for sd in sorted(service_dates):
            running = round(running - SERVICE[sd], 2)
        
        # Apply interest at month end
        interest_dates = [d for d in INTEREST.keys() if d.month == month_end.month]
        if len(interest_dates) != 1:
            print(f"Error: expected 1 interest date for {month_end}, found {interest_dates}")
            chain_ok = False
            continue
        d = interest_dates[0]
        running = round(running - INTEREST[d], 2)
        ok = abs(running - target) < 0.01
        print(f"{month_end} — interest {INTEREST[d]:.2f} + services {sum(SERVICE.get(sd,0) for sd in service_dates):.2f} => {running:.2f} | target {target:.2f} | {'OK' if ok else 'MISMATCH'}")
        if not ok:
            chain_ok = False

    if not chain_ok:
        print('Chain mismatch detected; aborting write.')
        return

    conn = get_conn()
    cur = conn.cursor()

    updates = 0
    for month_end, target in TARGETS:
        # Update interest row balance to month-end target
        idate = [d for d in INTEREST.keys() if d.month == month_end.month][0]
        iamnt = INTEREST[idate]
        cur.execute(
            """
            UPDATE banking_transactions
            SET balance = %s
            WHERE account_number = %s AND transaction_date = %s
              AND description ILIKE %s
              AND COALESCE(debit_amount,0) = %s
            """,
            (target, ACCOUNT, idate, 'OVERDRAFT INTEREST%', iamnt)
        )
        updates += cur.rowcount
        # Update service charge rows in October to the intermediate balance after service charge
        if month_end.month == 10:
            # Intermediate balance after service charge before interest is target + interest amount
            intermediate = round(target + INTEREST[idate], 2)
            for sd, samnt in SERVICE.items():
                if sd.month == 10:
                    cur.execute(
                        """
                        UPDATE banking_transactions
                        SET balance = %s
                        WHERE account_number = %s AND transaction_date = %s
                          AND description ILIKE %s
                          AND COALESCE(debit_amount,0) = %s
                        """,
                        (intermediate, ACCOUNT, sd, 'SERVICE CHARGE%', samnt)
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

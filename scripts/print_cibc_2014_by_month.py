import os
import psycopg2


def main():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    account = '0228362'  # CIBC

    conn = psycopg2.connect(host=host, dbname=name, user=user, password=password)
    cur = conn.cursor()

    months = [
        ('Jan', '2014-01-01', '2014-02-01'),
        ('Feb', '2014-02-01', '2014-03-01'),
        ('Mar', '2014-03-01', '2014-04-01'),
        ('Apr', '2014-04-01', '2014-05-01'),
        ('May', '2014-05-01', '2014-06-01'),
        ('Jun', '2014-06-01', '2014-07-01'),
        ('Jul', '2014-07-01', '2014-08-01'),
        ('Aug', '2014-08-01', '2014-09-01'),
        ('Sep', '2014-09-01', '2014-10-01'),
        ('Oct', '2014-10-01', '2014-11-01'),
        ('Nov', '2014-11-01', '2014-12-01'),
        ('Dec', '2014-12-01', '2015-01-01'),
    ]

    print('CIBC 2014 (account 0228362) month-by-month summary:')
    for label, start, end in months:
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= %s
              AND transaction_date < %s
            """,
            (account, start, end)
        )
        count, debits, credits = cur.fetchone()
        print(f"{label} 2014 — count: {count}, debits: {float(debits):.2f}, credits: {float(credits):.2f}")

    # Detailed breakdown for Jan-Aug to reconcile against PDFs
    print('\nDetailed breakdown (Jan-Aug):')
    for label, start, end in months[:8]:
        print(f"\n{label} 2014 details")
        # Withdrawals
        cur.execute(
            """
            SELECT to_char(transaction_date, 'YYYY-MM-DD'), description,
                   COALESCE(debit_amount,0) AS withdrawal
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= %s
              AND transaction_date < %s
              AND COALESCE(debit_amount,0) > 0
            ORDER BY transaction_date, transaction_id
            """,
            (account, start, end)
        )
        rows = cur.fetchall()
        total_w = 0.0
        for dt, desc, w in rows:
            total_w += float(w or 0)
            print(f"  {dt} W ${float(w):.2f} — {desc}")
        print(f"  Total withdrawals: ${total_w:.2f}")

        # Deposits
        cur.execute(
            """
            SELECT to_char(transaction_date, 'YYYY-MM-DD'), description,
                   COALESCE(credit_amount,0) AS deposit
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= %s
              AND transaction_date < %s
              AND COALESCE(credit_amount,0) > 0
            ORDER BY transaction_date, transaction_id
            """,
            (account, start, end)
        )
        rows = cur.fetchall()
        total_d = 0.0
        for dt, desc, d in rows:
            total_d += float(d or 0)
            print(f"  {dt} D ${float(d):.2f} — {desc}")
        print(f"  Total deposits: ${total_d:.2f}")

    # Sep–Dec summary details
    print('\nDetailed breakdown (Sep-Dec):')
    for label, start, end in months[8:]:
        print(f"\n{label} 2014 details")
        cur.execute(
            """
            SELECT to_char(transaction_date, 'YYYY-MM-DD'), description,
                   COALESCE(debit_amount,0), COALESCE(credit_amount,0)
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= %s
              AND transaction_date < %s
              AND (COALESCE(debit_amount,0) > 0 OR COALESCE(credit_amount,0) > 0)
            ORDER BY transaction_date, transaction_id
            """,
            (account, start, end)
        )
        rows = cur.fetchall()
        total_w = 0.0
        total_d = 0.0
        for dt, desc, w, d in rows:
            if w and float(w) > 0:
                total_w += float(w)
                print(f"  {dt} W ${float(w):.2f} — {desc}")
            if d and float(d) > 0:
                total_d += float(d)
                print(f"  {dt} D ${float(d):.2f} — {desc}")
        print(f"  Total withdrawals: ${total_w:.2f}")
        print(f"  Total deposits: ${total_d:.2f}")

    # Discrepancy summary vs PDF totals provided (enter expected withdrawals per month)
    expected_withdrawals = {
        'Jan': 115.42,
        'Feb': 58.24,
        'Mar': 117.27,
        'Apr': 110.94,
        'May': 114.85,
        'Jun': 114.83,
        'Jul': 118.94,
        'Aug': 121.07,
        'Sep': 67.96,
        'Oct': 71.44,
        'Nov': 70.37,
        'Dec': 73.97,
    }
    expected_deposits = {
        'Mar': 433.77,
        # other months show 0.00 in the screenshots
    }

    print('\nDiscrepancy summary (DB vs PDF):')
    for idx, (label, start, end) in enumerate(months):
        cur.execute(
            """
            SELECT COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= %s
              AND transaction_date < %s
            """,
            (account, start, end)
        )
        db_w, db_d = cur.fetchone()
        pdf_w = expected_withdrawals.get(label, None)
        pdf_d = expected_deposits.get(label, 0.0)
        diff_w = float(db_w) - (pdf_w if pdf_w is not None else 0.0)
        diff_d = float(db_d) - pdf_d
        print(f"{label}: DB W ${float(db_w):.2f} vs PDF W ${pdf_w if pdf_w is not None else 0.0:.2f} (Δ {diff_w:+.2f}); DB D ${float(db_d):.2f} vs PDF D ${pdf_d:.2f} (Δ {diff_d:+.2f})")

    conn.close()


if __name__ == '__main__':
    main()

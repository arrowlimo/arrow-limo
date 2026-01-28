import os
import argparse
from datetime import date
import psycopg2


ACCOUNT = '0228362'  # CIBC checking

# Expected month-end fee totals from statements (withdrawals) and deposits
MONTH_FIXES = {
    # label: (year, month, [(desc, amount)], deposit_amount or None)
    'Jan': (2014, 1, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 62.42),
        ('PAPER STMT FEE', 3.00),
    ], None),
    'Feb': (2014, 2, [
        ('OVERDRAFT INTEREST', 58.24),
    ], None),
    'Mar': (2014, 3, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 64.27),
        ('PAPER STMT FEE', 3.00),
    ], 433.77),
    'Apr': (2014, 4, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 57.94),
        ('PAPER STMT FEE', 3.00),
    ], None),
    'May': (2014, 5, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 61.85),
        ('PAPER STMT FEE', 3.00),
    ], None),
    'Jun': (2014, 6, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 61.83),
        ('PAPER STMT FEE', 3.00),
    ], None),
    'Jul': (2014, 7, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 65.94),
        ('PAPER STMT FEE', 3.00),
    ], None),
    'Aug': (2014, 8, [
        ('ACCOUNT FEE', 50.00),
        ('OVERDRAFT INTEREST', 68.07),
        ('PAPER STMT FEE', 3.00),
    ], None),
    'Sep': (2014, 9, [
        ('OVERDRAFT INTEREST', 67.96),
    ], None),
    'Oct': (2014, 10, [
        ('OVERDRAFT INTEREST', 71.44),
    ], None),
    'Nov': (2014, 11, [
        ('OVERDRAFT INTEREST', 70.37),
    ], None),
    'Dec': (2014, 12, [
        ('OVERDRAFT INTEREST', 73.97),
    ], None),
}


def end_of_month(y, m):
    # Days per month (not handling leap year here since only 2014 months used)
    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(y, m, days[m - 1])


def connect_db():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def ensure_backup(cur, label):
    backup_table = f"banking_transactions_cibc_2014_backup_{label}"
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = %s AND EXTRACT(YEAR FROM transaction_date) = 2014
    """, (ACCOUNT,))
    return backup_table


def current_month_totals(cur, y, m):
    cur.execute(
        """
        SELECT COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
        FROM banking_transactions
        WHERE account_number = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
        """,
        (ACCOUNT, y, m)
    )
    return cur.fetchone()


def upsert_month(cur, label, y, m, fees, deposit, apply=False):
    eom = end_of_month(y, m)
    planned = []

    # Targeted removal of known placeholder lines for early months (exact match by date+amount+pattern)
    if (y, m) == (2014, 1):
        cur.execute(
            """
            SELECT transaction_id, description, debit_amount FROM banking_transactions
            WHERE account_number = %s AND transaction_date = %s
              AND COALESCE(debit_amount,0) = 115.42 AND description ILIKE 'Cheque%'
            """,
            (ACCOUNT, eom)
        )
        for tid, desc, amt in cur.fetchall():
            planned.append(("delete", tid, desc, float(amt or 0)))
            if apply:
                cur.execute("DELETE FROM banking_transactions WHERE transaction_id = %s", (tid,))
    if (y, m) == (2014, 2):
        # Two lines: 61.15 and 1.00
        for amt in (61.15, 1.00):
            cur.execute(
                """
                SELECT transaction_id, description, debit_amount FROM banking_transactions
                WHERE account_number = %s AND transaction_date = %s
                  AND COALESCE(debit_amount,0) = %s AND description ILIKE 'Cheque%'
                """,
                (ACCOUNT, eom, amt)
            )
            for tid, desc, a in cur.fetchall():
                planned.append(("delete", tid, desc, float(a or 0)))
                if apply:
                    cur.execute("DELETE FROM banking_transactions WHERE transaction_id = %s", (tid,))
    if (y, m) == (2014, 3):
        cur.execute(
            """
            SELECT transaction_id, description, debit_amount FROM banking_transactions
            WHERE account_number = %s AND transaction_date = %s
              AND COALESCE(debit_amount,0) = 119.39 AND description ILIKE 'Cheque%'
            """,
            (ACCOUNT, eom)
        )
        for tid, desc, amt in cur.fetchall():
            planned.append(("delete", tid, desc, float(amt or 0)))
            if apply:
                cur.execute("DELETE FROM banking_transactions WHERE transaction_id = %s", (tid,))
    if (y, m) == (2014, 4):
        for amt in (177.00, 110.51):
            cur.execute(
                """
                SELECT transaction_id, description, debit_amount FROM banking_transactions
                WHERE account_number = %s AND transaction_date = %s
                  AND COALESCE(debit_amount,0) = %s AND description ILIKE 'Cheque%'
                """,
                (ACCOUNT, eom, amt)
            )
            for tid, desc, a in cur.fetchall():
                planned.append(("delete", tid, desc, float(a or 0)))
                if apply:
                    cur.execute("DELETE FROM banking_transactions WHERE transaction_id = %s", (tid,))
    if (y, m) == (2014, 5):
        cur.execute(
            """
            SELECT transaction_id, description, debit_amount FROM banking_transactions
            WHERE account_number = %s AND transaction_date = %s
              AND COALESCE(debit_amount,0) = 115.07 AND description ILIKE 'Cheque%'
            """,
            (ACCOUNT, eom)
        )
        for tid, desc, amt in cur.fetchall():
            planned.append(("delete", tid, desc, float(amt or 0)))
            if apply:
                cur.execute("DELETE FROM banking_transactions WHERE transaction_id = %s", (tid,))

    # Insert fee lines idempotently
    for desc, amt in fees:
        cur.execute(
            """
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = %s AND transaction_date = %s
              AND COALESCE(debit_amount,0) = %s AND description = %s
            """,
            (ACCOUNT, eom, amt, desc)
        )
        exists = cur.fetchone()
        if not exists:
            planned.append(("insert_withdrawal", eom.isoformat(), desc, amt))
            if apply:
                cur.execute(
                    """
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount
                    ) VALUES (%s, %s, %s, %s, NULL)
                    """,
                    (ACCOUNT, eom, desc, amt)
                )

    # Insert deposit if provided
    if deposit and deposit > 0:
        cur.execute(
            """
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = %s AND EXTRACT(YEAR FROM transaction_date) = %s
              AND EXTRACT(MONTH FROM transaction_date) = %s
              AND COALESCE(credit_amount,0) = %s
            ORDER BY transaction_id ASC LIMIT 1
            """,
            (ACCOUNT, y, m, deposit)
        )
        exists = cur.fetchone()
        if not exists:
            planned.append(("insert_deposit", eom.isoformat(), "CREDIT MEMO EFT credit from Global Payment", deposit))
            if apply:
                cur.execute(
                    """
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount
                    ) VALUES (%s, %s, %s, NULL, %s)
                    """,
                    (ACCOUNT, eom, "CREDIT MEMO EFT credit from Global Payment", deposit)
                )

    return planned


def main():
    parser = argparse.ArgumentParser(description='Fix CIBC 2014 fee and deposit entries (idempotent, with backup).')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run).')
    args = parser.parse_args()

    conn = connect_db()
    cur = conn.cursor()

    backup = ensure_backup(cur, 'pre_fix')
    print(f"Backup ensured: {backup}")

    total_planned = []
    for label, (y, m, fees, deposit) in MONTH_FIXES.items():
        db_w, db_d = current_month_totals(cur, y, m)
        target_w = sum(a for _, a in fees)
        target_d = deposit or 0.0
        print(f"\n{label} {y}: DB W {float(db_w):.2f} / target W {target_w:.2f}; DB D {float(db_d):.2f} / target D {target_d:.2f}")
        planned = upsert_month(cur, label, y, m, fees, deposit, apply=args.write)
        for action in planned:
            print('  PLAN:', action)
        total_planned.extend(planned)

    if args.write:
        conn.commit()
        print(f"\nApplied {len(total_planned)} changes.")
    else:
        conn.rollback()
        print(f"\nDRY-RUN complete. Planned changes: {len(total_planned)} (no DB writes).")

    conn.close()


if __name__ == '__main__':
    main()

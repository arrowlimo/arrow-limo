import os
import sys
import psycopg2


def main():
    if len(sys.argv) < 2:
        print("Usage: python print_cibc_year_by_month.py <year> [account_number]")
        return
    year = int(sys.argv[1])
    account = sys.argv[2] if len(sys.argv) > 2 else '0228362'

    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    conn = psycopg2.connect(host=host, dbname=name, user=user, password=password)
    cur = conn.cursor()

    months = [
        ('Jan', f'{year}-01-01', f'{year}-02-01'),
        ('Feb', f'{year}-02-01', f'{year}-03-01'),
        ('Mar', f'{year}-03-01', f'{year}-04-01'),
        ('Apr', f'{year}-04-01', f'{year}-05-01'),
        ('May', f'{year}-05-01', f'{year}-06-01'),
        ('Jun', f'{year}-06-01', f'{year}-07-01'),
        ('Jul', f'{year}-07-01', f'{year}-08-01'),
        ('Aug', f'{year}-08-01', f'{year}-09-01'),
        ('Sep', f'{year}-09-01', f'{year}-10-01'),
        ('Oct', f'{year}-10-01', f'{year}-11-01'),
        ('Nov', f'{year}-11-01', f'{year}-12-01'),
        ('Dec', f'{year}-12-01', f'{year+1}-01-01'),
    ]

    print(f'CIBC {year} (account {account}) month-by-month summary:')
    for label, start, end in months:
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0),
                   MIN(balance), MAX(balance),
                   COUNT(CASE WHEN COALESCE(debit_amount,0) <> 0 THEN 1 END),
                   COUNT(CASE WHEN COALESCE(credit_amount,0) <> 0 THEN 1 END)
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= %s
              AND transaction_date < %s
            """,
            (account, start, end)
        )
        row = cur.fetchone()
        count, debits, credits, min_bal, max_bal, nz_debits, nz_credits = row
        print(
            f"{label} {year} — count: {count}, debits: {float(debits):.2f} (nz {nz_debits}), "
            f"credits: {float(credits):.2f} (nz {nz_credits}), balance[min..max]: {min_bal}..{max_bal}"
        )

    conn.close()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Recalculate 2012 Scotia (account 903990106011) running balances with a fixed opening balance.
- Default opening balance: 40.00
- Recomputes balance = opening + SUM(credit - debit) in chronological order
- Creates a backup table before applying changes when --write is used
"""

import argparse
from datetime import datetime
import psycopg2

ACCOUNT = '903990106011'
START_DATE = '2012-01-01'
END_DATE = '2012-12-31'


def main():
    parser = argparse.ArgumentParser(description='Recalculate Scotia 2012 balances')
    parser.add_argument('--opening', type=float, default=40.00, help='Opening balance (default 40.00)')
    parser.add_argument('--write', action='store_true', help='Apply updates (default dry-run)')
    args = parser.parse_args()

    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()

    print('=' * 80)
    print('RECALCULATE SCOTIA 2012 BALANCES')
    print('=' * 80)
    print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, opening balance: {args.opening:.2f}')
    print('Mode:', 'WRITE (will update balances)' if args.write else 'DRY-RUN (no changes)')
    print()

    # Fetch rows in chronological order
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date BETWEEN %s AND %s
        ORDER BY transaction_date ASC, transaction_id ASC
        """,
        (ACCOUNT, START_DATE, END_DATE),
    )
    rows = cur.fetchall()
    if not rows:
        print('No rows found for Scotia 2012. Nothing to do.')
        cur.close(); conn.close(); return

    print(f'Loaded {len(rows):,} Scotia 2012 transactions')

    # Compute running balances
    running = args.opening
    new_balances = []  # list of (balance, transaction_id)
    for txn_id, txn_date, desc, debit, credit in rows:
        debit_val = float(debit) if debit else 0.0
        credit_val = float(credit) if credit else 0.0
        running += credit_val - debit_val
        new_balances.append((running, txn_id))

    final_balance = new_balances[-1][0]
    print(f'Computed final balance: {final_balance:.2f}')
    print()

    if args.write:
        # Backup table
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f"banking_transactions_scotia_2012_backup_{ts}"
        print(f'Creating backup table: {backup_table}')
        cur.execute(
            f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM banking_transactions
            WHERE account_number = %s AND transaction_date BETWEEN %s AND %s
            """,
            (ACCOUNT, START_DATE, END_DATE),
        )
        print(f'Backup created with {cur.rowcount:,} rows')
        print('Applying balance updates...')
        cur.executemany(
            "UPDATE banking_transactions SET balance = %s WHERE transaction_id = %s",
            new_balances,
        )
        print(f'Updated {cur.rowcount:,} rows')
        conn.commit()
        print('✅ Changes committed')
    else:
        print('DRY-RUN: No changes applied')

    cur.close(); conn.close()


if __name__ == '__main__':
    main()

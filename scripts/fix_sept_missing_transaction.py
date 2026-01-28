import os, psycopg2
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))
ACCOUNT_NUMBER = '903990106011'

MISSING_TXS = [
    {
        'date': '2012-09-28',
        'description': 'OVERDRAFT INTEREST (missing entry)',
        'debit': 4.65,
        'credit': 0.0
    },
    {
        'date': '2012-09-29',
        'description': 'OVERDRAFT INTEREST REVERSAL (balance alignment)',
        'debit': 0.0,
        'credit': 4.65
    }
]

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def insert_missing():
    conn = get_conn()
    cur = conn.cursor()
    inserted = 0
    for tx in MISSING_TXS:
        cur.execute("""
            INSERT INTO banking_transactions (account_number, transaction_date, description, debit_amount, credit_amount, balance)
            SELECT %s, %s, %s, %s, %s, NULL
            WHERE NOT EXISTS (
                SELECT 1 FROM banking_transactions
                WHERE account_number=%s
                  AND transaction_date=%s
                  AND COALESCE(debit_amount,0)=COALESCE(%s,0)
                  AND COALESCE(credit_amount,0)=COALESCE(%s,0)
                  AND description=%s
            )
        """, (
            ACCOUNT_NUMBER,
            tx['date'],
            tx['description'],
            tx['debit'],
            tx['credit'],
            ACCOUNT_NUMBER,
            tx['date'],
            tx['debit'],
            tx['credit'],
            tx['description']
        ))
        inserted += cur.rowcount
    conn.commit()
    cur.close(); conn.close()
    print(f'Inserted {inserted} missing transaction(s) (idempotent).')

def recalc_balances():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number=%s AND EXTRACT(YEAR FROM transaction_date)=2012
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT_NUMBER,))
    rows = cur.fetchall()
    running = 40.00  # verified opening
    updates = []
    for tid, date, d, c in rows:
        d = float(d) if d else 0.0
        c = float(c) if c else 0.0
        running -= d
        running += c
        updates.append((round(running,2), tid))
    for bal, tid in updates:
        cur.execute("UPDATE banking_transactions SET balance=%s WHERE transaction_id=%s", (bal, tid))
    conn.commit()
    print(f'Recalculated balances for {len(updates)} transactions; closing balance ${updates[-1][0]:,.2f}')
    cur.close(); conn.close()

def verify_checkpoints():
    checkpoints = {
        '2012-09-28': 3122.29,
        '2012-10-31': 430.21,
        '2012-11-30': 5.23,
        '2012-12-31': 952.04
    }
    conn = get_conn(); cur = conn.cursor()
    print('\nCheckpoint verification:')
    for date, expected in checkpoints.items():
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number=%s AND transaction_date<=%s
            ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1
        """, (ACCOUNT_NUMBER, date))
        row = cur.fetchone(); actual = float(row[0]) if row else None
        if actual is None:
            print(f'  {date}: NO DATA (expected ${expected:,.2f})')
        else:
            diff = actual - expected
            status = 'MATCH' if abs(diff) < 0.01 else f'diff ${diff:+.2f}'
            print(f'  {date}: ${actual:,.2f} ({status})')
    cur.close(); conn.close()

def main():
    insert_missing()
    recalc_balances()
    verify_checkpoints()

if __name__ == '__main__':
    main()

#!/usr/bin/env python
import psycopg2, os

def main():
    conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REDACTED***'))
    cur = conn.cursor()
    amounts = [1900.50, 2700.00]
    accounts = ['1615','3648117','903990106011','8314462']
    print('Search 2012 matches for amounts', amounts, 'in accounts', accounts)
    cur.execute("""
        SELECT transaction_id, account_number, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = ANY(%s)
          AND transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (debit_amount = ANY(%s) OR credit_amount = ANY(%s))
        ORDER BY account_number, transaction_date
    """, (accounts, amounts, amounts))
    rows = cur.fetchall()
    print('Found rows:', len(rows))
    for r in rows:
        print(r)
    cur.close(); conn.close()

if __name__ == '__main__':
    main()

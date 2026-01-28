#!/usr/bin/env python
import psycopg2, os

def main():
    conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REMOVED***'))
    cur = conn.cursor()
    cur.execute("SELECT transaction_id, account_number, transaction_date, description, check_number, debit_amount, credit_amount FROM banking_transactions WHERE check_number = '261' OR description ILIKE '%CHQ 261%' ORDER BY transaction_date")
    rows = cur.fetchall()
    print('Matches:', len(rows))
    for r in rows:
        print(r)
    cur.close(); conn.close()

if __name__ == '__main__':
    main()

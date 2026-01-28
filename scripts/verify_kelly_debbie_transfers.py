import psycopg2
from datetime import date

QUERY = """
SELECT transaction_id, account_number, transaction_date, description,
             debit_amount, credit_amount, balance
FROM banking_transactions
WHERE transaction_date BETWEEN %s AND %s
    AND (
                UPPER(description) LIKE '%%KELLY%%' OR
                UPPER(description) LIKE '%%DEBBIE%%'
            )
    AND (
                credit_amount IN (700,520)
                OR debit_amount IN (700,520)
            )
ORDER BY transaction_date, transaction_id;
"""

def main():
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
    cur = conn.cursor()
    start = date(2021,12,1)
    end = date(2021,12,31)
    cur.execute(QUERY, (start, end))
    rows = cur.fetchall()
    if not rows:
        print('No matching $700/$520 Kelly/Debbie transactions found in December 2021 window.')
    else:
        print('Matched transactions:')
        for r in rows:
            tid, acct, tdate, desc, debit, credit, bal = r
            print(f"{tdate} | id {tid} | acct {acct} | debit {debit or 0:.2f} | credit {credit or 0:.2f} | bal {bal or 0:.2f} | {desc}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Generic vendor text search in banking_transactions.
Usage: hardcoded for now to search 'WOODRIDGE' 2018-01-01..2020-12-31
"""
import psycopg2

def main():
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
    cur = conn.cursor()
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount, description
        FROM banking_transactions
        WHERE transaction_date BETWEEN DATE '2018-01-01' AND DATE '2020-12-31'
          AND UPPER(COALESCE(description,'')) LIKE '%%WOODRIDGE%%'
        ORDER BY transaction_date
    """)
    rows = cur.fetchall()
    print(f"Matches: {len(rows)}")
    for r in rows:
        tid, tdate, debit, credit, desc = r
        print(f"  {tdate}  ID {tid}  debit ${debit or 0:.2f}  credit ${credit or 0:.2f}\n    {desc[:180]}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

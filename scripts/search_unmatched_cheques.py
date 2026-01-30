#!/usr/bin/env python3
"""
Search for the 3 unmatched cheques in banking transactions.
"""

import psycopg2

UNMATCHED = [
    {'cheque_num': 215, 'date': '2012-03-19', 'payee': 'Deblown Algan', 'amount': 150.00},
    {'cheque_num': 216, 'date': '2012-03-19', 'payee': 'Sarah Odwald', 'amount': 100.00},
    {'cheque_num': 276, 'date': '2012-07-10', 'payee': 'Classico', 'amount': 1050.00},
]

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('SEARCHING FOR UNMATCHED CHEQUES IN BANKING')
    print('=' * 80)
    print()

    for cheque in UNMATCHED:
        print(f"Cheque {cheque['cheque_num']}: {cheque['date']} | ${cheque['amount']:,.2f} | {cheque['payee']}")
        
        # Search within ±7 days
        cur.execute('''
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE ABS(debit_amount - %s) < 0.01
            AND transaction_date BETWEEN (%s::date - interval '7 days')::date 
                                     AND (%s::date + interval '7 days')::date
            AND debit_amount > 0
            ORDER BY transaction_date
        ''', (cheque['amount'], cheque['date'], cheque['date']))
        
        results = cur.fetchall()
        
        if results:
            print(f"  Found {len(results)} potential matches:")
            for r in results:
                date_diff = abs((r[1] - cur.execute("SELECT %s::date", (cheque['date'],)) or cur.fetchone()[0]).days)
                print(f"    {r[0]}: {r[1]} | ${r[3]:,.2f} | {r[2][:60]}")
        else:
            print("  [FAIL] No matches found in ±7 days")
        
        print()

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from api import get_db_connection

def main():
    conn = get_db_connection(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM banking_transactions
            WHERE transaction_date >= '2013-01-01' AND transaction_date < '2014-01-01'
        """)
        total = cur.fetchone()[0]
        print(f"2013 banking_transactions: {total}")
        cur.execute("""
            SELECT account_number, COUNT(*) AS c,
                   MIN(transaction_date), MAX(transaction_date)
            FROM banking_transactions
            WHERE transaction_date >= '2013-01-01' AND transaction_date < '2014-01-01'
            GROUP BY account_number
            ORDER BY c DESC
        """)
        for acct, c, min_d, max_d in cur.fetchall():
            print(f"  {acct}: {c} from {min_d} to {max_d}")
    finally:
        cur.close(); conn.close()

if __name__ == '__main__':
    main()

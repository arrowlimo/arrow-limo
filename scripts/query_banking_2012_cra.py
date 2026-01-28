import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from api import get_db_connection

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(debit_amount),0), COALESCE(SUM(credit_amount),0)
            FROM banking_transactions
            WHERE transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
              AND LOWER(description) LIKE '%cra%'
        """)
        cnt, deb, cred = cur.fetchone()
        print(f"2012 CRA-like rows: {cnt} | debit={deb:.2f} | credit={cred:.2f}")
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
              AND LOWER(description) LIKE '%cra%'
            ORDER BY transaction_date
            LIMIT 10
        """)
        rows = cur.fetchall()
        for r in rows:
            print(r)
    finally:
        cur.close(); conn.close()

if __name__ == '__main__':
    main()

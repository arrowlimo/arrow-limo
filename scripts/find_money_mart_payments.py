"""
Find Money Mart payments of exactly $287.50 in banking_transactions
"""
import psycopg2

def main():
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    print("\nSearching banking_transactions for Money Mart debits of exactly $287.50 ...\n")
    cur.execute(
        """
        SELECT transaction_id, transaction_date,
               description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE debit_amount IS NOT NULL
          AND ROUND(debit_amount::numeric, 2) = 287.50
          AND (
                LOWER(description) LIKE '%money mart%'
             OR LOWER(description) LIKE '%national money mart%'
          )
        ORDER BY transaction_date
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("No exact $287.50 Money Mart debits found.")
    else:
        print(f"Found {len(rows)} matching transactions:\n")
        print(f"{'TXID':<10} {'Date':<12} {'Debit':>10}  {'Description'}")
        print('-'*80)
        for txid, tdate, desc, debit, credit in rows:
            print(f"{txid:<10} {str(tdate):<12} {debit:>10.2f}  {desc}")
    
    # Also report near matches within +/- $0.01 in case of rounding
    print("\nNear matches (+/- $0.01) for Money Mart ...\n")
    cur.execute(
        """
        SELECT transaction_id, transaction_date,
               description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE debit_amount IS NOT NULL
          AND debit_amount BETWEEN 287.49 AND 287.51
          AND (
                LOWER(description) LIKE '%money mart%'
             OR LOWER(description) LIKE '%national money mart%'
          )
        ORDER BY transaction_date
        """
    )
    near = cur.fetchall()
    if not near:
        print("No near matches within $0.01 found.")
    else:
        print(f"Found {len(near)} near matches:\n")
        print(f"{'TXID':<10} {'Date':<12} {'Debit':>10}  {'Description'}")
        print('-'*80)
        for txid, tdate, desc, debit, credit in near:
            print(f"{txid:<10} {str(tdate):<12} {debit:>10.2f}  {desc}")
    conn.close()

if __name__ == '__main__':
    main()

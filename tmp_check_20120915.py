import psycopg2, os

def main():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REMOVED***'),
    )
    cur = conn.cursor()
    date_str = '2012-09-15'
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date = %s AND debit_amount BETWEEN 130 AND 140
        ORDER BY transaction_id
        """,
        (date_str,),
    )
    banking = cur.fetchall()
    print("Banking candidates (2012-09-15 ~135):")
    for b in banking:
        print(f"  id={b[0]} | amt={b[3]:.2f} | desc={b[2]}")

    if banking:
        ids = tuple(b[0] for b in banking)
        cur.execute(
            """
            SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, r.banking_transaction_id
            FROM receipts r
            WHERE r.banking_transaction_id IN %s
            ORDER BY r.banking_transaction_id, r.receipt_id
            """,
            (ids,),
        )
        receipts = cur.fetchall()
        print("\nLinked receipts:")
        for r in receipts:
            print(f"  tx={r[4]} | receipt={r[0]} | date={r[1]} | vendor={r[2]} | amt={r[3]:.2f}")

        cur.execute(
            """
            SELECT bt.transaction_id, bt.debit_amount,
                   COALESCE(SUM(r.gross_amount),0) AS linked_total,
                   bt.debit_amount - COALESCE(SUM(r.gross_amount),0) AS unallocated
            FROM banking_transactions bt
            LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
            WHERE bt.transaction_id IN %s
            GROUP BY bt.transaction_id, bt.debit_amount
            ORDER BY bt.transaction_id
            """,
            (ids,),
        )
        bal = cur.fetchall()
        print("\nAllocation summary:")
        for row in bal:
            print(f"  id={row[0]} | debit={row[1]:.2f} | linked={row[2]:.2f} | unallocated={row[3]:.2f}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

import psycopg2, os

def main():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REMOVED***'),
    )
    cur = conn.cursor()

    tx_id = 69336
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_id = %s
        """,
        (tx_id,),
    )
    bt = cur.fetchone()
    print("Banking transaction 69336:")
    print(bt)

    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id
        FROM receipts
        WHERE banking_transaction_id = %s
        ORDER BY receipt_id
        """,
        (tx_id,),
    )
    receipts = cur.fetchall()
    print("\nReceipts linked to 69336:")
    for r in receipts:
        print(r)

    cur.execute(
        """
        SELECT bt.transaction_id, bt.debit_amount,
               COALESCE(SUM(r.gross_amount),0) AS linked_total,
               bt.debit_amount - COALESCE(SUM(r.gross_amount),0) AS unallocated
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.transaction_id = %s
        GROUP BY bt.transaction_id, bt.debit_amount
        """,
        (tx_id,),
    )
    summary = cur.fetchone()
    print("\nAllocation summary:")
    print(summary)

    cur.close(); conn.close()

if __name__ == "__main__":
    main()

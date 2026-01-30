import os
import psycopg2

def get_conn():
    DB_HOST=os.getenv('DB_HOST','localhost')
    DB_NAME=os.getenv('DB_NAME','almsdata')
    DB_USER=os.getenv('DB_USER','postgres')
    DB_PASSWORD=os.getenv('DB_PASSWORD','***REDACTED***')
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def main():
    conn = get_conn()
    cur = conn.cursor()
    print('=== Per-year totals (2014-2017) for 0228362 vs 903990106011 ===')
    cur.execute(
        """
        SELECT account_number,
               EXTRACT(YEAR FROM transaction_date)::int AS yr,
               COUNT(*) AS txns,
               COALESCE(SUM(debit_amount),0) AS debits,
               COALESCE(SUM(credit_amount),0) AS credits
        FROM banking_transactions
        WHERE account_number IN ('0228362','903990106011')
          AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2014 AND 2017
        GROUP BY account_number, yr
        ORDER BY account_number, yr;
        """
    )
    for r in cur.fetchall():
        print(r)

    print('\n=== Cross-account linkage audit (receipts \u2194 banking) ===')
    cur.execute(
        """
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id = 2;
        """
    )
    print('CIBC→Scotia links:', cur.fetchone()[0])
    cur.execute(
        """
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id = 1;
        """
    )
    print('Scotia→CIBC links:', cur.fetchone()[0])

    print('\n=== Sample anomalies (limit 5 each) ===')
    cur.execute(
        """
        SELECT bt.transaction_id, bt.account_number, bt.transaction_date, bt.description, r.receipt_id, r.mapped_bank_account_id
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '0228362' AND r.mapped_bank_account_id = 2
        LIMIT 5;
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print('CIBC txn linked to Scotia receipt:', r)
    else:
        print('No CIBC→Scotia anomalies found.')

    cur.execute(
        """
        SELECT bt.transaction_id, bt.account_number, bt.transaction_date, bt.description, r.receipt_id, r.mapped_bank_account_id
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        JOIN receipts r ON r.receipt_id = bm.receipt_id
        WHERE bt.account_number = '903990106011' AND r.mapped_bank_account_id = 1
        LIMIT 5;
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print('Scotia txn linked to CIBC receipt:', r)
    else:
        print('No Scotia→CIBC anomalies found.')

    cur.close(); conn.close()

if __name__ == '__main__':
    main()

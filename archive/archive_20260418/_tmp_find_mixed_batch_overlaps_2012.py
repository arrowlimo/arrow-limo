import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

batch = 'cibc_v5_import_20260302'

cur.execute(
    """
    WITH b AS (
        SELECT
            transaction_id,
            account_number,
            transaction_date,
            COALESCE(posted_date::text, '') AS posted_date,
            COALESCE(description, '') AS description,
            COALESCE(debit_amount, 0) AS debit_amount,
            COALESCE(credit_amount, 0) AS credit_amount,
            COALESCE(check_number, '') AS check_number,
            import_batch
        FROM banking_transactions
        WHERE import_batch = %s
          AND transaction_date >= DATE '2012-01-01'
          AND transaction_date < DATE '2013-01-01'
          AND account_number IN ('0228362', '1615')
    ),
    g AS (
        SELECT
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            check_number,
            COUNT(*) AS cnt,
            COUNT(DISTINCT account_number) AS acct_cnt,
            STRING_AGG(DISTINCT account_number, ', ' ORDER BY account_number) AS accts
        FROM b
        GROUP BY 1,2,3,4,5,6
        HAVING COUNT(DISTINCT account_number) > 1
    )
    SELECT
        COUNT(*) AS overlap_groups,
        COALESCE(SUM(cnt),0) AS overlap_rows
    FROM g
    """,
    (batch,)
)
summary = cur.fetchone()
print('mixed_batch_overlap_groups', summary['overlap_groups'])
print('mixed_batch_overlap_rows', summary['overlap_rows'])

cur.execute(
    """
    WITH b AS (
        SELECT
            transaction_id,
            account_number,
            transaction_date,
            COALESCE(posted_date::text, '') AS posted_date,
            COALESCE(description, '') AS description,
            COALESCE(debit_amount, 0) AS debit_amount,
            COALESCE(credit_amount, 0) AS credit_amount,
            COALESCE(check_number, '') AS check_number,
            import_batch
        FROM banking_transactions
        WHERE import_batch = %s
          AND transaction_date >= DATE '2012-01-01'
          AND transaction_date < DATE '2013-01-01'
          AND account_number IN ('0228362', '1615')
    ),
    g AS (
        SELECT
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            check_number,
            COUNT(*) AS cnt,
            COUNT(DISTINCT account_number) AS acct_cnt
        FROM b
        GROUP BY 1,2,3,4,5,6
        HAVING COUNT(DISTINCT account_number) > 1
    )
    SELECT
        b.transaction_id,
        b.account_number,
        b.transaction_date,
        b.posted_date,
        b.description,
        b.debit_amount,
        b.credit_amount,
        b.check_number
    FROM b
    JOIN g
      ON g.transaction_date = b.transaction_date
     AND g.posted_date = b.posted_date
     AND g.description = b.description
     AND g.debit_amount = b.debit_amount
     AND g.credit_amount = b.credit_amount
     AND g.check_number = b.check_number
    ORDER BY b.transaction_date, b.description, b.debit_amount, b.account_number
    LIMIT 200
    """,
    (batch,)
)

print('\nSample overlapped rows:')
for r in cur.fetchall():
    print(
        r['transaction_id'],
        r['account_number'],
        r['transaction_date'],
        r['description'],
        float(r['debit_amount']),
        float(r['credit_amount']),
        r['check_number'],
    )

conn.close()

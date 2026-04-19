import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Exact composite match across different accounts for 2012.
cur.execute(
    """
    WITH base AS (
        SELECT
            transaction_id,
            account_number,
            transaction_date,
            posted_date,
            COALESCE(description, '') AS description,
            COALESCE(debit_amount, 0) AS debit_amount,
            COALESCE(credit_amount, 0) AS credit_amount,
            COALESCE(check_number, '') AS check_number,
            COALESCE(is_transfer, false) AS is_transfer,
            COALESCE(is_nsf_charge, false) AS is_nsf_charge,
            created_at,
            source_file,
            import_batch
        FROM banking_transactions
        WHERE transaction_date >= DATE '2012-01-01'
          AND transaction_date < DATE '2013-01-01'
    ),
    acc8362 AS (
        SELECT *
        FROM base
        WHERE account_number = '0228362'
    ),
    others AS (
        SELECT *
        FROM base
        WHERE account_number <> '0228362'
    ),
    exact_match AS (
        SELECT
            a.transaction_id AS tx_8362,
            a.account_number AS acct_8362,
            b.transaction_id AS tx_other,
            b.account_number AS acct_other,
            a.transaction_date,
            a.posted_date,
            a.description,
            a.debit_amount,
            a.credit_amount,
            a.check_number,
            a.is_transfer,
            a.is_nsf_charge,
            a.source_file AS source_8362,
            b.source_file AS source_other,
            a.import_batch AS batch_8362,
            b.import_batch AS batch_other
        FROM acc8362 a
        JOIN others b
          ON a.transaction_date = b.transaction_date
         AND COALESCE(a.posted_date::text, '') = COALESCE(b.posted_date::text, '')
         AND a.description = b.description
         AND a.debit_amount = b.debit_amount
         AND a.credit_amount = b.credit_amount
         AND a.check_number = b.check_number
    )
    SELECT
        COUNT(*) AS exact_cross_matches,
        COUNT(DISTINCT tx_8362) AS affected_8362_rows,
        COUNT(DISTINCT acct_other) AS other_accounts_count
    FROM exact_match
    """
)

s = cur.fetchone()
print("2012 8362 cross-account exact matches")
print(f"exact_cross_matches: {s['exact_cross_matches']}")
print(f"affected_8362_rows: {s['affected_8362_rows']}")
print(f"other_accounts_count: {s['other_accounts_count']}")

cur.execute(
    """
    WITH base AS (
        SELECT
            transaction_id,
            account_number,
            transaction_date,
            posted_date,
            COALESCE(description, '') AS description,
            COALESCE(debit_amount, 0) AS debit_amount,
            COALESCE(credit_amount, 0) AS credit_amount,
            COALESCE(check_number, '') AS check_number,
            COALESCE(is_transfer, false) AS is_transfer,
            COALESCE(is_nsf_charge, false) AS is_nsf_charge,
            created_at,
            source_file,
            import_batch
        FROM banking_transactions
        WHERE transaction_date >= DATE '2012-01-01'
          AND transaction_date < DATE '2013-01-01'
    ),
    acc8362 AS (
        SELECT * FROM base WHERE account_number = '0228362'
    ),
    others AS (
        SELECT * FROM base WHERE account_number <> '0228362'
    ),
    exact_match AS (
        SELECT
            a.transaction_id AS tx_8362,
            b.transaction_id AS tx_other,
            b.account_number AS acct_other,
            a.transaction_date,
            a.posted_date,
            a.description,
            a.debit_amount,
            a.credit_amount,
            a.check_number,
            a.is_transfer,
            a.is_nsf_charge,
            a.source_file AS source_8362,
            b.source_file AS source_other,
            a.import_batch AS batch_8362,
            b.import_batch AS batch_other
        FROM acc8362 a
        JOIN others b
          ON a.transaction_date = b.transaction_date
         AND COALESCE(a.posted_date::text, '') = COALESCE(b.posted_date::text, '')
         AND a.description = b.description
         AND a.debit_amount = b.debit_amount
         AND a.credit_amount = b.credit_amount
         AND a.check_number = b.check_number
    )
    SELECT *
    FROM exact_match
    ORDER BY transaction_date, description, debit_amount
    LIMIT 120
    """
)

print("\nSample matches:")
for r in cur.fetchall():
    print(
        r['tx_8362'],
        r['tx_other'],
        r['acct_other'],
        r['transaction_date'],
        r['description'],
        float(r['debit_amount']),
        float(r['credit_amount']),
        r['check_number'],
        r['is_transfer'],
        r['is_nsf_charge'],
    )

conn.close()

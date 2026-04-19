import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# source_hash overlaps for 8362 vs others in 2012
cur.execute(
    """
    WITH a AS (
      SELECT transaction_id, account_number, transaction_date, description, debit_amount, credit_amount, source_hash, transaction_uid
      FROM banking_transactions
      WHERE transaction_date >= DATE '2012-01-01'
        AND transaction_date < DATE '2013-01-01'
        AND account_number = '0228362'
    ),
    b AS (
      SELECT transaction_id, account_number, transaction_date, description, debit_amount, credit_amount, source_hash, transaction_uid
      FROM banking_transactions
      WHERE transaction_date >= DATE '2012-01-01'
        AND transaction_date < DATE '2013-01-01'
        AND account_number <> '0228362'
    )
    SELECT
      COUNT(*) AS hash_matches,
      COUNT(DISTINCT a.transaction_id) AS affected_8362
    FROM a
    JOIN b ON a.source_hash IS NOT NULL AND a.source_hash <> '' AND a.source_hash = b.source_hash
    """
)
r = cur.fetchone()
print('source_hash_matches', r['hash_matches'])
print('source_hash_affected_8362', r['affected_8362'])

cur.execute(
    """
    WITH a AS (
      SELECT transaction_id, account_number, transaction_date, description, debit_amount, credit_amount, source_hash, transaction_uid
      FROM banking_transactions
      WHERE transaction_date >= DATE '2012-01-01'
        AND transaction_date < DATE '2013-01-01'
        AND account_number = '0228362'
    ),
    b AS (
      SELECT transaction_id, account_number, transaction_date, description, debit_amount, credit_amount, source_hash, transaction_uid
      FROM banking_transactions
      WHERE transaction_date >= DATE '2012-01-01'
        AND transaction_date < DATE '2013-01-01'
        AND account_number <> '0228362'
    )
    SELECT
      COUNT(*) AS uid_matches,
      COUNT(DISTINCT a.transaction_id) AS affected_8362
    FROM a
    JOIN b ON a.transaction_uid IS NOT NULL AND a.transaction_uid <> '' AND a.transaction_uid = b.transaction_uid
    """
)
r = cur.fetchone()
print('transaction_uid_matches', r['uid_matches'])
print('transaction_uid_affected_8362', r['affected_8362'])

conn.close()

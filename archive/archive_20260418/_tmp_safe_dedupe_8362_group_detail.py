import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

protected_text = """
(
    COALESCE(description, '') ILIKE '%nsf%'
    OR COALESCE(description, '') ILIKE '%stop payment%'
    OR COALESCE(description, '') ILIKE '%correction%'
    OR COALESCE(description, '') ILIKE '%correcting%'
    OR COALESCE(description, '') ILIKE '%return%'
)
"""

cur.execute(
    f"""
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
            COALESCE(source_file, '') AS source_file,
            COALESCE(import_batch, '') AS import_batch,
            COALESCE(is_transfer, false) AS is_transfer,
            COALESCE(is_nsf_charge, false) AS is_nsf_charge,
            created_at
        FROM banking_transactions
        WHERE account_number = '0228362'
    ),
    protected AS (
        SELECT transaction_id
        FROM base
        WHERE is_nsf_charge = true
           OR is_transfer = true
           OR {protected_text}
    ),
    eligible AS (
        SELECT *
        FROM base
        WHERE transaction_id NOT IN (SELECT transaction_id FROM protected)
    ),
    dupes AS (
        SELECT
            account_number,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            check_number,
            COUNT(*) AS cnt
        FROM eligible
        GROUP BY
            account_number,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            check_number
        HAVING COUNT(*) > 1
    )
    SELECT
        d.cnt,
        e.transaction_id,
        e.transaction_date,
        e.posted_date,
        e.description,
        e.debit_amount,
        e.credit_amount,
        e.check_number,
        e.source_file,
        e.import_batch,
        e.created_at
    FROM eligible e
    JOIN dupes d
      ON d.account_number = e.account_number
     AND d.transaction_date = e.transaction_date
     AND COALESCE(d.posted_date::text, '') = COALESCE(e.posted_date::text, '')
     AND d.description = e.description
     AND d.debit_amount = e.debit_amount
     AND d.credit_amount = e.credit_amount
     AND d.check_number = e.check_number
    ORDER BY d.cnt DESC, e.transaction_date, e.description, e.debit_amount, e.transaction_id
    LIMIT 300
    """
)

rows = cur.fetchall()
print(f"rows_returned: {len(rows)}")
for r in rows:
    print(
        int(r['cnt']),
        r['transaction_id'],
        r['transaction_date'],
        r['posted_date'],
        r['description'],
        float(r['debit_amount']),
        float(r['credit_amount']),
        r['check_number'],
        r['source_file'],
        r['import_batch'],
        r['created_at'],
    )

conn.close()

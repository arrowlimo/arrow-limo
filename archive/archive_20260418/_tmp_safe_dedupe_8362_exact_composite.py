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
            COALESCE(is_transfer, false) AS is_transfer,
            COALESCE(is_nsf_charge, false) AS is_nsf_charge
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
    composite_dupes AS (
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
        (SELECT COUNT(*) FROM base) AS total_8362,
        (SELECT COUNT(*) FROM protected) AS protected_rows,
        (SELECT COUNT(*) FROM eligible) AS eligible_rows,
        (SELECT COUNT(*) FROM composite_dupes) AS duplicate_groups,
        (SELECT COALESCE(SUM(cnt), 0) FROM composite_dupes) AS duplicate_rows
    """
)

s = cur.fetchone()
print("8362 EXACT-COMPOSITE DRY RUN")
print(f"total_8362_rows: {s['total_8362']}")
print(f"protected_rows: {s['protected_rows']}")
print(f"eligible_rows: {s['eligible_rows']}")
print(f"composite_duplicate_groups: {s['duplicate_groups']}")
print(f"composite_duplicate_rows: {s['duplicate_rows']}")

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
            COALESCE(is_transfer, false) AS is_transfer,
            COALESCE(is_nsf_charge, false) AS is_nsf_charge
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
    composite_dupes AS (
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
        d.transaction_date,
        d.posted_date,
        d.description,
        d.debit_amount,
        d.credit_amount,
        d.check_number
    FROM composite_dupes d
    ORDER BY d.cnt DESC, d.transaction_date
    LIMIT 40
    """
)

print("\nTop duplicate groups (eligible only):")
for r in cur.fetchall():
    print(
        int(r['cnt']),
        r['transaction_date'],
        r['posted_date'],
        r['description'],
        float(r['debit_amount']),
        float(r['credit_amount']),
        r['check_number'],
    )

conn.close()

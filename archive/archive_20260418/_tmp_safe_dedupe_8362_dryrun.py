import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# User safety rules:
# 1) Only consider account 8362
# 2) Never treat NSF / stop payment / correction / transfer rows as duplicates
# 3) If it exists as multiple rows in banking, treat as real unless proven duplicate by exact same UID/hash
# 4) Fees can repeat with same amount; do not dedupe by amount-only

protected_text = """
(
    COALESCE(description, '') ILIKE '%%nsf%%'
    OR COALESCE(description, '') ILIKE '%%stop payment%%'
    OR COALESCE(description, '') ILIKE '%%correction%%'
    OR COALESCE(description, '') ILIKE '%%correcting%%'
    OR COALESCE(description, '') ILIKE '%%return%%'
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
            description,
            debit_amount,
            credit_amount,
            transaction_uid,
            source_hash,
            is_transfer,
            is_nsf_charge
        FROM banking_transactions
        WHERE account_number = '0228362'
    ),
    protected AS (
        SELECT *
        FROM base
        WHERE COALESCE(is_nsf_charge, false) = true
           OR COALESCE(is_transfer, false) = true
           OR {protected_text}
    ),
    eligible AS (
        SELECT *
        FROM base
        WHERE transaction_id NOT IN (SELECT transaction_id FROM protected)
    ),
    exact_uid_dupes AS (
        SELECT transaction_uid, COUNT(*) AS cnt
        FROM eligible
        WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''
        GROUP BY transaction_uid
        HAVING COUNT(*) > 1
    ),
    exact_hash_dupes AS (
        SELECT source_hash, COUNT(*) AS cnt
        FROM eligible
        WHERE source_hash IS NOT NULL AND TRIM(source_hash) <> ''
        GROUP BY source_hash
        HAVING COUNT(*) > 1
    )
    SELECT
        (SELECT COUNT(*) FROM base) AS total_8362,
        (SELECT COUNT(*) FROM protected) AS protected_rows,
        (SELECT COUNT(*) FROM eligible) AS eligible_rows,
        (SELECT COALESCE(SUM(cnt), 0) FROM exact_uid_dupes) AS uid_duplicate_rows,
        (SELECT COUNT(*) FROM exact_uid_dupes) AS uid_duplicate_groups,
        (SELECT COALESCE(SUM(cnt), 0) FROM exact_hash_dupes) AS hash_duplicate_rows,
        (SELECT COUNT(*) FROM exact_hash_dupes) AS hash_duplicate_groups
    """
)

summary = cur.fetchone()
print("SAFE DEDUPE DRY RUN (8362 ONLY)")
print(f"total_8362_rows: {summary['total_8362']}")
print(f"protected_rows: {summary['protected_rows']}")
print(f"eligible_rows: {summary['eligible_rows']}")
print(f"uid_duplicate_groups: {summary['uid_duplicate_groups']}")
print(f"uid_duplicate_rows: {summary['uid_duplicate_rows']}")
print(f"hash_duplicate_groups: {summary['hash_duplicate_groups']}")
print(f"hash_duplicate_rows: {summary['hash_duplicate_rows']}")

# Show sample exact-UID duplicate groups only (safest signal)
cur.execute(
    f"""
    WITH base AS (
        SELECT
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            transaction_uid,
            source_hash,
            is_transfer,
            is_nsf_charge
        FROM banking_transactions
        WHERE account_number = '0228362'
    ),
    protected AS (
        SELECT *
        FROM base
        WHERE COALESCE(is_nsf_charge, false) = true
           OR COALESCE(is_transfer, false) = true
           OR {protected_text}
    ),
    eligible AS (
        SELECT *
        FROM base
        WHERE transaction_id NOT IN (SELECT transaction_id FROM protected)
    ),
    dupes AS (
        SELECT transaction_uid
        FROM eligible
        WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''
        GROUP BY transaction_uid
        HAVING COUNT(*) > 1
    )
    SELECT e.transaction_uid, e.transaction_id, e.transaction_date, e.description, e.debit_amount, e.credit_amount
    FROM eligible e
    JOIN dupes d ON d.transaction_uid = e.transaction_uid
    ORDER BY e.transaction_uid, e.transaction_date
    LIMIT 50
    """
)

rows = cur.fetchall()
print("\nSample exact UID duplicate rows (eligible only):")
for r in rows:
    print(
        r['transaction_uid'],
        r['transaction_id'],
        r['transaction_date'],
        r['description'],
        float(r['debit_amount'] or 0),
        float(r['credit_amount'] or 0),
    )

conn.close()

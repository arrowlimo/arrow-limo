import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

acct = '0228362'

print('=== 8362 RECEIPT REQUIREMENT + DUPLICATION AUDIT ===\n')

# Rule for "requires receipt" (conservative):
# - debit transaction
# - not transfer
# - not NSF charge
# - not obvious banking/admin entry text
# This is a review queue, not an auto-delete/update rule.
require_filter = """
account_number = %(acct)s
AND COALESCE(debit_amount,0) > 0
AND COALESCE(is_transfer,false) = false
AND COALESCE(is_nsf_charge,false) = false
AND COALESCE(description,'') NOT ILIKE '%%nsf%%'
AND COALESCE(description,'') NOT ILIKE '%%stop payment%%'
AND COALESCE(description,'') NOT ILIKE '%%correction%%'
AND COALESCE(description,'') NOT ILIKE '%%service charge%%'
AND COALESCE(description,'') NOT ILIKE '%%monthly fee%%'
AND COALESCE(description,'') NOT ILIKE '%%bank fee%%'
AND COALESCE(description,'') NOT ILIKE '%%interest%%'
"""

cur.execute(
    f"""
    SELECT
      COUNT(*) AS tx_count,
      COALESCE(SUM(debit_amount),0) AS tx_amount
    FROM banking_transactions
    WHERE {require_filter}
    """,
    {'acct': acct}
)
base = cur.fetchone()
print('Receipt-required debit transactions (rule-based):')
print(f"  count: {base['tx_count']}")
print(f"  amount: ${float(base['tx_amount']):,.2f}")

# Missing receipt links (both direct and reconciled link empty)
cur.execute(
    f"""
    SELECT
      COUNT(*) AS missing_count,
      COALESCE(SUM(debit_amount),0) AS missing_amount
    FROM banking_transactions
    WHERE {require_filter}
      AND receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
    """,
    {'acct': acct}
)
miss = cur.fetchone()
print('\nMissing receipt links (receipt_id + reconciled_receipt_id both null):')
print(f"  count: {miss['missing_count']}")
print(f"  amount: ${float(miss['missing_amount']):,.2f}")

# Heffner specifically
cur.execute(
    """
    SELECT
      COUNT(*) AS heffner_count,
      COALESCE(SUM(debit_amount),0) AS heffner_amount,
      MIN(transaction_date) AS min_date,
      MAX(transaction_date) AS max_date
    FROM banking_transactions
    WHERE account_number = %s
      AND COALESCE(description,'') ILIKE '%%heffner%%'
    """,
    (acct,)
)
hef = cur.fetchone()
print('\nHeffner transactions in 8362:')
print(f"  count: {hef['heffner_count']}")
print(f"  amount: ${float(hef['heffner_amount']):,.2f}")
print(f"  date range: {hef['min_date']} -> {hef['max_date']}")

# Heffner exact duplicate groups (same date, description, debit, credit, check)
cur.execute(
    """
    WITH h AS (
      SELECT
        transaction_id,
        transaction_date,
        COALESCE(posted_date::text,'') AS posted_date,
        COALESCE(description,'') AS description,
        COALESCE(debit_amount,0) AS debit_amount,
        COALESCE(credit_amount,0) AS credit_amount,
        COALESCE(check_number,'') AS check_number,
        receipt_id,
        reconciled_receipt_id
      FROM banking_transactions
      WHERE account_number = %s
        AND COALESCE(description,'') ILIKE '%%heffner%%'
    ),
    g AS (
      SELECT
        transaction_date, posted_date, description, debit_amount, credit_amount, check_number,
        COUNT(*) AS cnt
      FROM h
      GROUP BY 1,2,3,4,5,6
      HAVING COUNT(*) > 1
    )
    SELECT
      COUNT(*) AS dup_groups,
      COALESCE(SUM(cnt),0) AS dup_rows
    FROM g
    """,
    (acct,)
)
hef_dup = cur.fetchone()
print('\nHeffner exact-duplicate check:')
print(f"  duplicate groups: {hef_dup['dup_groups']}")
print(f"  duplicate rows: {hef_dup['dup_rows']}")

# Auto withdrawal / cheque duplicate sanity check (exact same transaction signature)
cur.execute(
    """
    WITH x AS (
      SELECT
        transaction_id,
        transaction_date,
        COALESCE(posted_date::text,'') AS posted_date,
        COALESCE(description,'') AS description,
        COALESCE(debit_amount,0) AS debit_amount,
        COALESCE(credit_amount,0) AS credit_amount,
        COALESCE(check_number,'') AS check_number,
        COALESCE(is_transfer,false) AS is_transfer,
        COALESCE(is_nsf_charge,false) AS is_nsf_charge
      FROM banking_transactions
      WHERE account_number = %s
        AND (
          COALESCE(description,'') ILIKE '%%auto%%'
          OR COALESCE(description,'') ILIKE '%%withdrawal%%'
          OR COALESCE(description,'') ILIKE '%%chq%%'
          OR COALESCE(description,'') ILIKE '%%cheque%%'
        )
        AND COALESCE(is_transfer,false) = false
        AND COALESCE(is_nsf_charge,false) = false
    ),
    g AS (
      SELECT
        transaction_date, posted_date, description, debit_amount, credit_amount, check_number,
        COUNT(*) AS cnt
      FROM x
      GROUP BY 1,2,3,4,5,6
      HAVING COUNT(*) > 1
    )
    SELECT COUNT(*) AS dup_groups, COALESCE(SUM(cnt),0) AS dup_rows FROM g
    """,
    (acct,)
)
auto_dup = cur.fetchone()
print('\nAuto-withdrawal/cheque exact-duplicate check (non-NSF, non-transfer):')
print(f"  duplicate groups: {auto_dup['dup_groups']}")
print(f"  duplicate rows: {auto_dup['dup_rows']}")

# Show top missing-receipt rows to review
cur.execute(
    f"""
    SELECT
      transaction_id, transaction_date, description, debit_amount, credit_amount,
      check_number, receipt_id, reconciled_receipt_id, source_file, import_batch
    FROM banking_transactions
    WHERE {require_filter}
      AND receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
    ORDER BY debit_amount DESC, transaction_date DESC
    LIMIT 40
    """,
    {'acct': acct}
)
rows = cur.fetchall()
print('\nTop missing-receipt review rows:')
for r in rows:
    print(
      r['transaction_id'], r['transaction_date'], r['description'],
      float(r['debit_amount'] or 0), float(r['credit_amount'] or 0),
      r['check_number'], r['receipt_id'], r['reconciled_receipt_id'],
      r['source_file'], r['import_batch']
    )

conn.close()

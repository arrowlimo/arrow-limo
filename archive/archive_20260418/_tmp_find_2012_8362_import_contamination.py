import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# 1) 2012 rows in 8362 by source file / batch
cur.execute(
    """
    SELECT
      COALESCE(source_file, '<NULL>') AS source_file,
      COALESCE(import_batch, '<NULL>') AS import_batch,
      COUNT(*) AS cnt,
      COALESCE(SUM(debit_amount),0) AS debit_sum,
      COALESCE(SUM(credit_amount),0) AS credit_sum,
      MIN(transaction_date) AS min_dt,
      MAX(transaction_date) AS max_dt
    FROM banking_transactions
    WHERE account_number = '0228362'
      AND transaction_date >= DATE '2012-01-01'
      AND transaction_date < DATE '2013-01-01'
    GROUP BY 1,2
    ORDER BY cnt DESC
    LIMIT 80
    """
)

print("2012 8362 source/batch groups:")
for r in cur.fetchall():
    print(
        r['cnt'],
        r['source_file'],
        r['import_batch'],
        r['min_dt'],
        r['max_dt'],
        float(r['debit_sum'] or 0),
        float(r['credit_sum'] or 0),
    )

# 2) Any import_batch that contains multiple account numbers (strong contamination signal)
cur.execute(
    """
    SELECT
      COALESCE(import_batch, '<NULL>') AS import_batch,
      COUNT(*) AS rows_total,
      COUNT(DISTINCT account_number) AS acct_count,
      STRING_AGG(DISTINCT account_number, ', ' ORDER BY account_number) AS accounts,
      MIN(transaction_date) AS min_dt,
      MAX(transaction_date) AS max_dt
    FROM banking_transactions
    WHERE transaction_date >= DATE '2012-01-01'
      AND transaction_date < DATE '2013-01-01'
    GROUP BY 1
    HAVING COUNT(DISTINCT account_number) > 1
    ORDER BY rows_total DESC
    LIMIT 60
    """
)

rows = cur.fetchall()
print("\n2012 mixed-account import batches:")
print(f"count: {len(rows)}")
for r in rows:
    print(
        r['import_batch'],
        r['rows_total'],
        r['acct_count'],
        r['accounts'],
        r['min_dt'],
        r['max_dt'],
    )

# 3) Rows in 8362 whose source_file text hints other account ids
cur.execute(
    """
    SELECT
      transaction_id,
      transaction_date,
      account_number,
      description,
      debit_amount,
      credit_amount,
      source_file,
      import_batch
    FROM banking_transactions
    WHERE account_number = '0228362'
      AND transaction_date >= DATE '2012-01-01'
      AND transaction_date < DATE '2013-01-01'
      AND (
        COALESCE(source_file,'') ILIKE '%1615%'
        OR COALESCE(source_file,'') ILIKE '%3648117%'
        OR COALESCE(source_file,'') ILIKE '%903990106011%'
      )
    ORDER BY transaction_date, transaction_id
    LIMIT 150
    """
)

rows = cur.fetchall()
print("\n2012 8362 rows with source_file hinting other accounts:")
print(f"count: {len(rows)}")
for r in rows:
    print(
        r['transaction_id'],
        r['transaction_date'],
        r['description'],
        float(r['debit_amount'] or 0),
        float(r['credit_amount'] or 0),
        r['source_file'],
        r['import_batch'],
    )

conn.close()

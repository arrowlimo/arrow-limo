import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

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
        COALESCE(source_file,'') AS source_file,
        COALESCE(import_batch,'') AS import_batch,
        COALESCE(is_transfer,false) AS is_transfer,
        COALESCE(is_nsf_charge,false) AS is_nsf_charge
      FROM banking_transactions
      WHERE account_number = '0228362'
        AND COALESCE(description,'') ILIKE '%%heffner%%'
    ),
    g AS (
      SELECT
        transaction_date, posted_date, description, debit_amount, credit_amount, check_number,
        COUNT(*) AS cnt,
        STRING_AGG(DISTINCT source_file, ' | ' ORDER BY source_file) AS srcs,
        STRING_AGG(DISTINCT import_batch, ' | ' ORDER BY import_batch) AS batches
      FROM h
      WHERE is_transfer = false
        AND is_nsf_charge = false
      GROUP BY 1,2,3,4,5,6
      HAVING COUNT(*) > 1
    )
    SELECT *
    FROM g
    ORDER BY transaction_date, debit_amount
    """
)
rows = cur.fetchall()
print(f"heffner_duplicate_groups: {len(rows)}")
for r in rows:
    print(
        r['transaction_date'],
        r['description'],
        float(r['debit_amount']),
        int(r['cnt']),
        r['srcs'],
        r['batches'],
    )

conn.close()

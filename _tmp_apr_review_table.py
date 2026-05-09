from datetime import date, timedelta
import os
import psycopg2

TARGETS = [
    (date(2012, 4, 2), 4067.00),
    (date(2012, 4, 9), 2893.00),
    (date(2012, 4, 23), 3703.69),
    (date(2012, 4, 27), 3330.88),
]
WINDOW_BEFORE_DAYS = 2
WINDOW_AFTER_DAYS = 21
MERCHANT_KEYWORDS = ["MERCH", "GLOBAL", "VISA", "MCARD", "ACARD", "VCARD", "DEPOSIT"]

pwd = os.environ.get("DB_PASSWORD")
if not pwd:
    raise RuntimeError("DB_PASSWORD not set")

conn = psycopg2.connect(host=os.getenv('DB_HOST', os.getenv('NEON_DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech')), port=5432, dbname=os.getenv('DB_NAME', os.getenv('NEON_DB_NAME', 'neondb')), user=os.getenv('DB_USER', os.getenv('NEON_DB_USER', 'neondb_owner')), password=pwd)
cur = conn.cursor()

for d, target in TARGETS:
    w_start = d - timedelta(days=WINDOW_BEFORE_DAYS)
    w_end = d + timedelta(days=WINDOW_AFTER_DAYS)

    cur.execute("""
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS credit_amount,
               COALESCE(debit_amount,0)::float AS debit_amount, COALESCE(description,'') AS description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount,0) > 0
        ORDER BY ABS(COALESCE(credit_amount,0)::float - %s), transaction_date, transaction_id
        LIMIT 8
    """, (w_start, w_end, target))
    closest = cur.fetchall()

    cur.execute("""
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS credit_amount,
               COALESCE(debit_amount,0)::float AS debit_amount, COALESCE(description,'') AS description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount,0) > 0
          AND (
              UPPER(COALESCE(description,'')) LIKE '%%MERCH%%' OR
              UPPER(COALESCE(description,'')) LIKE '%%GLOBAL%%' OR
              UPPER(COALESCE(description,'')) LIKE '%%VISA%%' OR
              UPPER(COALESCE(description,'')) LIKE '%%MCARD%%' OR
              UPPER(COALESCE(description,'')) LIKE '%%ACARD%%' OR
              UPPER(COALESCE(description,'')) LIKE '%%VCARD%%' OR
              UPPER(COALESCE(description,'')) LIKE '%%DEPOSIT%%'
          )
        ORDER BY ABS(COALESCE(credit_amount,0)::float - %s), transaction_date, transaction_id
        LIMIT 5
    """, (w_start, w_end, target))
    merch = cur.fetchall()

    cur.execute("""
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS credit_amount,
               COALESCE(debit_amount,0)::float AS debit_amount, COALESCE(description,'') AS description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(debit_amount,0) > 0
        ORDER BY COALESCE(debit_amount,0)::float DESC, transaction_date, transaction_id
        LIMIT 5
    """, (w_start, w_end))
    debits = cur.fetchall()

    cur.execute("""
        SELECT transaction_id, transaction_date, COALESCE(description,'') AS description
        FROM banking_transactions
        WHERE transaction_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
          AND ABS(COALESCE(credit_amount,0)::float - %s) < 0.005
        ORDER BY transaction_date, transaction_id
    """, (target,))
    exact = cur.fetchall()

    print(f"TARGET {d} amount={target:.2f} window=[{w_start},{w_end}]")
    print("closest_credits_top8:")
    if closest:
        for r in closest:
            print(f"  {r[0]} | {r[1]} | cr={r[2]:.2f} | db={r[3]:.2f} | {r[4]}")
    else:
        print("  (none)")

    print("merchant_like_top5:")
    if merch:
        for r in merch:
            print(f"  {r[0]} | {r[1]} | cr={r[2]:.2f} | db={r[3]:.2f} | {r[4]}")
    else:
        print("  (none)")

    print("debits_top5_desc:")
    if debits:
        for r in debits:
            print(f"  {r[0]} | {r[1]} | cr={r[2]:.2f} | db={r[3]:.2f} | {r[4]}")
    else:
        print("  (none)")

    print("exact_2012_credit_matches:")
    if exact:
        for r in exact:
            print(f"  {r[0]} | {r[1]} | {r[2]}")
    else:
        print("  (none)")
    print("-")

cur.close()
conn.close()

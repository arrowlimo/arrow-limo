from datetime import date, timedelta
import itertools
import os
import psycopg2

TARGETS = [
    (date(2012, 5, 1),  1147.36),
    (date(2012, 5, 2),  2423.75),
    (date(2012, 5, 3),   406.00),
    (date(2012, 5, 4),  1142.25),
    (date(2012, 5, 7),  1825.52),  # corrected from 1825.25    (date(2012, 5, 8), 3402.74),
    (date(2012, 5, 10), 801.00),
    (date(2012, 5, 11), 1465.54),
    (date(2012, 5, 14), 5476.26),
    (date(2012, 5, 15), 500.00),
    (date(2012, 5, 16), 1833.51),
    (date(2012, 5, 18), 2376.08),
    (date(2012, 5, 22), 198.23),
    (date(2012, 5, 23), 2558.75),
    (date(2012, 5, 24), 655.00),
    (date(2012, 5, 25), 1699.00),
    (date(2012, 5, 28), 3213.25),
    (date(2012, 5, 29), 3443.48),
    (date(2012, 5, 30), 0.01),
    (date(2012, 5, 31), 2930.00),
]

db_password = os.environ.get("DB_PASSWORD")
if not db_password:
    raise RuntimeError("Set DB_PASSWORD in the environment before running this script.")

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', os.getenv('NEON_DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech')), port=5432, dbname=os.getenv('DB_NAME', os.getenv('NEON_DB_NAME', 'neondb')),
    user=os.getenv('DB_USER', os.getenv('NEON_DB_USER', 'neondb_owner')), password=db_password,
)
cur = conn.cursor()

CARD_FILTER = """
  AND (
      UPPER(COALESCE(description,'')) LIKE '%%VCARD%%'
   OR UPPER(COALESCE(description,'')) LIKE '%%MCARD%%'
   OR UPPER(COALESCE(description,'')) LIKE '%%ACARD%%'
   OR UPPER(COALESCE(description,'')) LIKE '%%DCARD%%'
   OR UPPER(COALESCE(description,'')) LIKE '%%CREDIT MEMO%%'
   OR UPPER(COALESCE(description,'')) LIKE '%%GBL%%'
   OR UPPER(COALESCE(description,'')) LIKE '%%GLOBAL%%'
  )
"""

print("date,target,match_type,matched_sum,components")
matched_total = 0.0

for d, amt in TARGETS:
    if abs(amt) < 0.005:
        print(f"{d},{amt:.2f},zero,0.00,")
        continue

    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount,0) > 0
          {CARD_FILTER}
        ORDER BY transaction_date, transaction_id
        """,
        (d - timedelta(days=1), d + timedelta(days=2)),
    )
    rows_all = cur.fetchall()
    rows = [r for r in rows_all if r[2] <= amt + 0.005]
    rows.sort(key=lambda r, target=amt: abs(target - r[2]))
    rows = rows[:40]

    # 1. Same-day sum
    same_day = [r for r in rows_all if r[1] == d]
    same_day_sum = sum(r[2] for r in same_day)
    if abs(same_day_sum - amt) < 0.005 and same_day:
        matched_total += amt
        comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in same_day)
        print(f"{d},{amt:.2f},same_day_sum,{amt:.2f},{comp}")
        continue

    # 2. Adjacent ±1 day
    adj_found = False
    for offset in (-1, +1):
        adj_d = d + timedelta(days=offset)
        cur.execute(
            f"""
            SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
            FROM banking_transactions
            WHERE transaction_date = %s AND COALESCE(credit_amount,0) > 0
            {CARD_FILTER}
            ORDER BY transaction_id
            """,
            (adj_d,),
        )
        adj_rows = cur.fetchall()
        for r in adj_rows:
            if abs(r[2] - amt) < 0.005:
                matched_total += amt
                comp = f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}"
                print(f"{d},{amt:.2f},adj_exact({offset:+d}),{amt:.2f},{comp}")
                adj_found = True
                break
        if adj_found:
            break
        adj_sum = sum(r[2] for r in adj_rows)
        if abs(adj_sum - amt) < 0.005 and adj_rows:
            matched_total += amt
            comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in adj_rows)
            print(f"{d},{amt:.2f},adj_day_sum({offset:+d}),{amt:.2f},{comp}")
            adj_found = True
            break
    if adj_found:
        continue

    # 3. Exact single row
    exact = [r for r in rows if abs(r[2] - amt) < 0.005]
    if exact:
        r = exact[0]
        matched_total += amt
        comp = f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}"
        print(f"{d},{amt:.2f},exact,{amt:.2f},{comp}")
        continue

    # 4-9. Combos 2..7
    found = False
    labels = ["pair","triple","quad","penta","hexa","hepta"]
    for n in range(2, 8):
        pool = rows[:max(20, n * 4)]
        for combo in itertools.combinations(pool, n):
            if abs(sum(r[2] for r in combo) - amt) < 0.005:
                matched_total += amt
                comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in combo)
                print(f"{d},{amt:.2f},{labels[n-2]},{amt:.2f},{comp}")
                found = True
                break
        if found:
            break

    if not found:
        print(f"{d},{amt:.2f},unresolved,0.00,")

stmt_total = sum(a for _, a in TARGETS)
print(f"TOTAL,{stmt_total:.2f},matched,{matched_total:.2f},variance,{stmt_total-matched_total:.2f}")

# Fee: May 2012 total billed = $1,721.82, debited June 2012
cur.execute(
    """
    SELECT transaction_id, transaction_date, COALESCE(debit_amount,0), description
    FROM banking_transactions
    WHERE transaction_date BETWEEN DATE '2012-06-01' AND DATE '2012-06-10'
      AND COALESCE(debit_amount,0) IN (1721.82, 1695.59, 1138.21)
    ORDER BY transaction_date, transaction_id
    """
)
print("FEE_ROWS")
for r in cur.fetchall():
    print(f"  {r}")

cur.close()
conn.close()

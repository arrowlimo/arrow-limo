from datetime import date, timedelta

import os

import os

TARGETS = [
    (date(2012, 4, 2), 4067.00),
    (date(2012, 4, 5), 817.75),
    (date(2012, 4, 9), 2893.00),
    (date(2012, 4, 10), 405.00),
    (date(2012, 4, 11), 843.50),
    (date(2012, 4, 16), 500.00),
    (date(2012, 4, 17), 495.50),
    (date(2012, 4, 18), 3426.75),
    (date(2012, 4, 19), 350.00),
    (date(2012, 4, 20), 505.00),
    (date(2012, 4, 23), 3703.69),
    (date(2012, 4, 24), 256.00),
    (date(2012, 4, 27), 3330.88),
]

conn = psycopg2.connect(host=os.getenv('DB_HOST', os.getenv('NEON_DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech')), port=5432, dbname=os.getenv('DB_NAME', os.getenv('NEON_DB_NAME', 'neondb')), user=os.getenv('DB_USER', os.getenv('NEON_DB_USER', 'neondb_owner')), password=os.getenv('DB_PASSWORD', os.getenv('NEON_DB_PASSWORD', '')))
cur = conn.cursor()

print("date,target,match_type,matched_sum,components")
matched_total = 0.0

for d, amt in TARGETS:
    cur.execute(
        """
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount,0) > 0
        ORDER BY transaction_date, transaction_id
        """,
        (d, d + timedelta(days=7)),
    )
    rows_all = cur.fetchall()
    rows = [r for r in rows_all if r[2] <= amt + 0.005]
    rows.sort(key=lambda r: abs(amt - r[2]))
    rows = rows[:40]

    exact = [r for r in rows if abs(r[2] - amt) < 0.005]
    if exact:
        r = exact[0]
        matched_total += amt
        comp = f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}"
        print(f"{d},{amt:.2f},exact,{amt:.2f},{comp}")
        continue

    found = False
    for r1, r2 in itertools.combinations(rows, 2):
        s = r1[2] + r2[2]
        if abs(s - amt) < 0.005:
            matched_total += amt
            comp = (
                f"{r1[0]}:{r1[1]}:{r1[2]:.2f}:{r1[3]} + "
                f"{r2[0]}:{r2[1]}:{r2[2]:.2f}:{r2[3]}"
            )
            print(f"{d},{amt:.2f},pair,{amt:.2f},{comp}")
            found = True
            break
    if found:
        continue

    rows3 = rows[:30]
    for r1, r2, r3 in itertools.combinations(rows3, 3):
        s = r1[2] + r2[2] + r3[2]
        if abs(s - amt) < 0.005:
            matched_total += amt
            comp = (
                f"{r1[0]}:{r1[1]}:{r1[2]:.2f}:{r1[3]} + "
                f"{r2[0]}:{r2[1]}:{r2[2]:.2f}:{r2[3]} + "
                f"{r3[0]}:{r3[1]}:{r3[2]:.2f}:{r3[3]}"
            )
            print(f"{d},{amt:.2f},triple,{amt:.2f},{comp}")
            found = True
            break

    if not found:
        print(f"{d},{amt:.2f},unresolved,0.00,")

stmt_total = sum(a for _, a in TARGETS)
print(f"TOTAL,{stmt_total:.2f},matched,{matched_total:.2f},variance,{stmt_total-matched_total:.2f}")

# Fee check
cur.execute(
    """
    SELECT transaction_id, transaction_date, COALESCE(credit_amount,0), COALESCE(debit_amount,0), description
    FROM banking_transactions
    WHERE transaction_date BETWEEN DATE '2012-05-01' AND DATE '2012-05-10'
      AND (COALESCE(debit_amount,0)=1170.45 OR COALESCE(credit_amount,0)=1170.45)
    ORDER BY transaction_date, transaction_id
    """
)
rows = cur.fetchall()
print("FEE_ROWS")
for r in rows:
    print(r)

cur.close()
conn.close()

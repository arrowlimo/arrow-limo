
import os
from datetime import date, timedelta

import os

targets = [
    (date(2012, 6, 1), 308.00),
    (date(2012, 6, 4), 7013.95),
    (date(2012, 6, 5), 3585.50),
    (date(2012, 6, 7), 705.00),
    (date(2012, 6, 8), 683.25),
    (date(2012, 6, 11), 3370.86),
    (date(2012, 6, 12), 2233.75),
    (date(2012, 6, 13), 1149.50),
    (date(2012, 6, 15), 544.50),
    (date(2012, 6, 18), 2868.81),
    (date(2012, 6, 19), 2608.40),
    (date(2012, 6, 20), 312.73),
    (date(2012, 6, 25), 3405.57),
    (date(2012, 6, 27), 198.44),
    (date(2012, 6, 28), 800.50),
]

conn = psycopg2.connect(host=os.getenv('DB_HOST', os.getenv('NEON_DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech')), port=5432, dbname=os.getenv('DB_NAME', os.getenv('NEON_DB_NAME', 'neondb')), user=os.getenv('DB_USER', os.getenv('NEON_DB_USER', 'neondb_owner')), password=os.getenv('DB_PASSWORD', os.getenv('NEON_DB_PASSWORD', '')))
cur = conn.cursor()

for d, amount in targets:
    cur.execute(
        """
        SELECT transaction_id, transaction_date, COALESCE(credit_amount, 0)::float AS c, description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount, 0) > 0
        ORDER BY transaction_date, transaction_id
        """,
        (d, d + timedelta(days=7)),
    )
    rows = cur.fetchall()

    exact = [r for r in rows if abs(r[2] - amount) < 0.005]
    if exact:
        r = exact[0]
        print(f"{d} {amount:.2f} = exact {r[2]:.2f} id {r[0]} {r[1]} {r[3]}")
        continue

    found = False
    for r1, r2 in itertools.combinations(rows, 2):
        s = r1[2] + r2[2]
        if abs(s - amount) < 0.005:
            print(f"{d} {amount:.2f} = pair {r1[2]:.2f}+{r2[2]:.2f} ids {r1[0]},{r2[0]}")
            found = True
            break
    if found:
        continue

    rows2 = rows[:40]
    for r1, r2, r3 in itertools.combinations(rows2, 3):
        s = r1[2] + r2[2] + r3[2]
        if abs(s - amount) < 0.005:
            print(f"{d} {amount:.2f} = triple {r1[2]:.2f}+{r2[2]:.2f}+{r3[2]:.2f} ids {r1[0]},{r2[0]},{r3[0]}")
            found = True
            break

    if not found:
        print(f"{d} {amount:.2f} = unresolved")

cur.close()
conn.close()

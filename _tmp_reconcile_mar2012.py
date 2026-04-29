from datetime import date, timedelta
import itertools
import os
import psycopg2

TARGETS = [
    (date(2012, 3, 1), 1650.00),
    (date(2012, 3, 2), 135.00),
    (date(2012, 3, 5), 880.00),
    (date(2012, 3, 6), 205.00),
    (date(2012, 3, 7), 680.00),
    (date(2012, 3, 8), 1516.00),
    (date(2012, 3, 9), 162.75),
    (date(2012, 3, 12), 230.00),
    (date(2012, 3, 13), 1427.50),
    (date(2012, 3, 14), 1187.67),
    (date(2012, 3, 15), 535.00),
    (date(2012, 3, 16), 1455.00),
    (date(2012, 3, 19), 1536.00),
    (date(2012, 3, 20), 0.00),
    (date(2012, 3, 21), 970.00),
    (date(2012, 3, 22), 837.00),
    (date(2012, 3, 26), 1118.00),
    (date(2012, 3, 28), 1338.70),
    (date(2012, 3, 29), 243.75),
    (date(2012, 3, 30), 205.00),
]

WINDOW_DAYS = 14

db_password = os.environ.get("DB_PASSWORD")
if not db_password:
    raise RuntimeError("Set DB_PASSWORD in the environment before running this script.")

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password=db_password,
)
cur = conn.cursor()

print("date,target,match_type,matched_sum,components")
matched_total = 0.0

for d, amt in TARGETS:
    if abs(amt) < 0.005:
        print(f"{d},{amt:.2f},zero,0.00,")
        continue

    cur.execute(
        """
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount,0) > 0
        ORDER BY transaction_date, transaction_id
        """,
        (d, d + timedelta(days=WINDOW_DAYS)),
    )
    rows_all = cur.fetchall()
    rows = [r for r in rows_all if r[2] <= amt + 0.005]
    rows.sort(key=lambda r, target=amt: abs(target - r[2]))
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
    if found:
        continue

    rows4 = rows[:24]
    for r1, r2, r3, r4 in itertools.combinations(rows4, 4):
        s = r1[2] + r2[2] + r3[2] + r4[2]
        if abs(s - amt) < 0.005:
            matched_total += amt
            comp = (
                f"{r1[0]}:{r1[1]}:{r1[2]:.2f}:{r1[3]} + "
                f"{r2[0]}:{r2[1]}:{r2[2]:.2f}:{r2[3]} + "
                f"{r3[0]}:{r3[1]}:{r3[2]:.2f}:{r3[3]} + "
                f"{r4[0]}:{r4[1]}:{r4[2]:.2f}:{r4[3]}"
            )
            print(f"{d},{amt:.2f},quad,{amt:.2f},{comp}")
            found = True
            break

    if not found:
        print(f"{d},{amt:.2f},unresolved,0.00,")

stmt_total = sum(a for _, a in TARGETS)
print(f"TOTAL,{stmt_total:.2f},matched,{matched_total:.2f},variance,{stmt_total-matched_total:.2f}")

# Fee check from Mar statement (debited following month): $791.87
cur.execute(
    """
    SELECT transaction_id, transaction_date, COALESCE(credit_amount,0), COALESCE(debit_amount,0), description
    FROM banking_transactions
    WHERE transaction_date BETWEEN DATE '2012-04-01' AND DATE '2012-04-10'
      AND (COALESCE(debit_amount,0)=791.87 OR COALESCE(credit_amount,0)=791.87)
    ORDER BY transaction_date, transaction_id
    """
)
rows = cur.fetchall()
print("FEE_ROWS")
for r in rows:
    print(r)

cur.close()
conn.close()

from datetime import date, timedelta
import itertools
import os
import psycopg2

TARGETS = [
    (date(2012, 1, 3), 9884.49),
    (date(2012, 1, 4), 1483.37),
    (date(2012, 1, 5), 1283.24),
    (date(2012, 1, 6), 205.00),
    (date(2012, 1, 9), 205.00),
    (date(2012, 1, 11), 585.00),
    (date(2012, 1, 12), 261.00),
    (date(2012, 1, 16), 2662.73),
    (date(2012, 1, 17), 150.00),
    (date(2012, 1, 18), 175.00),
    (date(2012, 1, 19), 793.25),
    (date(2012, 1, 20), 134.38),
    (date(2012, 1, 23), 175.00),
    (date(2012, 1, 24), 370.00),
    (date(2012, 1, 26), 325.00),
    (date(2012, 1, 30), 3781.75),
    (date(2012, 1, 31), 0.00),
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

# Fee check from Jan statement (debited following month): $1,244.81
cur.execute(
    """
    SELECT transaction_id, transaction_date, COALESCE(credit_amount,0), COALESCE(debit_amount,0), description
    FROM banking_transactions
    WHERE transaction_date BETWEEN DATE '2012-02-01' AND DATE '2012-02-10'
      AND (COALESCE(debit_amount,0)=1244.81 OR COALESCE(credit_amount,0)=1244.81)
    ORDER BY transaction_date, transaction_id
    """
)
rows = cur.fetchall()
print("FEE_ROWS")
for r in rows:
    print(r)

cur.close()
conn.close()

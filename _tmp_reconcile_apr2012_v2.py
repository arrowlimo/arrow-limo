from datetime import date, timedelta
import itertools
import os
import psycopg2

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
    (date(2012, 4, 26), 0.00),
    (date(2012, 4, 27), 3330.88),
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
          AND (
              UPPER(COALESCE(description,'')) LIKE '%%VCARD%%'
           OR UPPER(COALESCE(description,'')) LIKE '%%MCARD%%'
           OR UPPER(COALESCE(description,'')) LIKE '%%ACARD%%'
           OR UPPER(COALESCE(description,'')) LIKE '%%DCARD%%'
           OR UPPER(COALESCE(description,'')) LIKE '%%CREDIT MEMO%%'
           OR UPPER(COALESCE(description,'')) LIKE '%%GBL%%'
           OR UPPER(COALESCE(description,'')) LIKE '%%GLOBAL%%'
          )
        ORDER BY transaction_date, transaction_id
        """,
        (d, d + timedelta(days=WINDOW_DAYS)),
    )
    rows_all = cur.fetchall()
    rows = [r for r in rows_all if r[2] <= amt + 0.005]
    rows.sort(key=lambda r, target=amt: abs(target - r[2]))
    rows = rows[:40]

    # Check if ALL credit rows on the exact statement date sum to target
    same_day = [r for r in rows_all if r[1] == d]
    same_day_sum = sum(r[2] for r in same_day)
    if abs(same_day_sum - amt) < 0.005 and same_day:
        matched_total += amt
        comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in same_day)
        print(f"{d},{amt:.2f},same_day_sum,{amt:.2f},{comp}")
        continue

    # ±1 day: look for exact single row or exact subset-sum on adjacent date
    adj_found = False
    for offset in (-1, +1):
        adj_d = d + timedelta(days=offset)
        cur.execute(
            """
            SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
            FROM banking_transactions
            WHERE transaction_date = %s
              AND COALESCE(credit_amount,0) > 0
            ORDER BY transaction_id
            """,
            (adj_d,),
        )
        adj_rows = cur.fetchall()
        if not adj_rows:
            continue
        # exact single row on adjacent date
        for r in adj_rows:
            if abs(r[2] - amt) < 0.005:
                matched_total += amt
                comp = f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}"
                print(f"{d},{amt:.2f},adj_exact({offset:+d}),{amt:.2f},{comp}")
                adj_found = True
                break
        if adj_found:
            break
        # whole-day sum on adjacent date
        adj_sum = sum(r[2] for r in adj_rows)
        if abs(adj_sum - amt) < 0.005:
            matched_total += amt
            comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in adj_rows)
            print(f"{d},{amt:.2f},adj_day_sum({offset:+d}),{amt:.2f},{comp}")
            adj_found = True
            break
    if adj_found:
        continue

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
    if found:
        continue

    rows5 = rows[:20]
    for r1, r2, r3, r4, r5 in itertools.combinations(rows5, 5):
        s = r1[2] + r2[2] + r3[2] + r4[2] + r5[2]
        if abs(s - amt) < 0.005:
            matched_total += amt
            comp = (
                f"{r1[0]}:{r1[1]}:{r1[2]:.2f}:{r1[3]} + "
                f"{r2[0]}:{r2[1]}:{r2[2]:.2f}:{r2[3]} + "
                f"{r3[0]}:{r3[1]}:{r3[2]:.2f}:{r3[3]} + "
                f"{r4[0]}:{r4[1]}:{r4[2]:.2f}:{r4[3]} + "
                f"{r5[0]}:{r5[1]}:{r5[2]:.2f}:{r5[3]}"
            )
            print(f"{d},{amt:.2f},penta,{amt:.2f},{comp}")
            found = True
            break
    if found:
        continue

    rows6 = rows[:25]
    for combo in itertools.combinations(rows6, 6):
        if abs(sum(r[2] for r in combo) - amt) < 0.005:
            matched_total += amt
            comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in combo)
            print(f"{d},{amt:.2f},hexa,{amt:.2f},{comp}")
            found = True
            break
    if found:
        continue

    rows7 = rows[:25]
    for combo in itertools.combinations(rows7, 7):
        if abs(sum(r[2] for r in combo) - amt) < 0.005:
            matched_total += amt
            comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in combo)
            print(f"{d},{amt:.2f},hepta,{amt:.2f},{comp}")
            found = True
            break
    if found:
        continue

    # 2-day non-AMEX check: GP batches exclude AMEX (separate network)
    # Sum all VCARD/MCARD/DCARD rows on D and D+1
    cur.execute(
        """
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
        FROM banking_transactions
        WHERE transaction_date IN (%s, %s)
          AND COALESCE(credit_amount,0) > 0
          AND UPPER(COALESCE(description,'')) NOT LIKE '%%ACARD%%'
        ORDER BY transaction_date, transaction_id
        """,
        (d, d + timedelta(days=1)),
    )
    two_day = cur.fetchall()
    two_day_sum = sum(r[2] for r in two_day)
    if abs(two_day_sum - amt) < 0.005 and two_day:
        matched_total += amt
        comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in two_day)
        print(f"{d},{amt:.2f},two_day_nonAmex,{amt:.2f},{comp}")
        found = True

    if not found:
        print(f"{d},{amt:.2f},unresolved,0.00,")

stmt_total = sum(a for _, a in TARGETS)
print(f"TOTAL,{stmt_total:.2f},matched,{matched_total:.2f},variance,{stmt_total-matched_total:.2f}")

# Fee check from Apr statement (debited following month): $1,170.45
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

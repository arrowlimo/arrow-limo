from datetime import date, timedelta
import itertools
import os
import psycopg2

TARGETS = [
    (date(2012, 6, 1),   308.00),
    (date(2012, 6, 4),  7013.95),
    (date(2012, 6, 5),  3585.50),
    (date(2012, 6, 7),   705.00),
    (date(2012, 6, 8),   683.25),
    (date(2012, 6, 11), 3370.86),
    (date(2012, 6, 12), 2233.75),
    (date(2012, 6, 13), 1149.50),
    (date(2012, 6, 15),  544.50),
    (date(2012, 6, 18), 2668.81),  # non-funded 450 assumed; verify if unresolved
    (date(2012, 6, 19), 2808.40),
    (date(2012, 6, 20),  312.73),
    (date(2012, 6, 25), 3405.57),
    (date(2012, 6, 27),  198.44),
    (date(2012, 6, 28),  800.50),
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
jun04_05_bundle = False
jun18_19_bundle = False

for d, amt in TARGETS:
    if abs(amt) < 0.005:
        print(f"{d},{amt:.2f},zero,0.00,")
        continue

    # CIBC posts Jun 4 + Jun 5 GP funded deposits together on Jun 5.
    if d == date(2012, 6, 4):
        cur.execute(
            """
            SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
            FROM banking_transactions
            WHERE transaction_date BETWEEN DATE '2012-06-04' AND DATE '2012-06-05'
              AND COALESCE(credit_amount,0) > 0
              AND (
                  UPPER(COALESCE(description,'')) LIKE '%%VCARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%MCARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%DCARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%CREDIT MEMO%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%GBL%%'
              )
            ORDER BY transaction_id
            """
        )
        bundle_rows = cur.fetchall()
        bundle_sum = sum(r[2] for r in bundle_rows)
        if abs(bundle_sum - (7013.95 + 3585.50)) < 0.005:
            matched_total += amt
            comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in bundle_rows)
            print(f"{d},{amt:.2f},two_day_bundle(part1),{amt:.2f},{comp}")
            jun04_05_bundle = True
            continue

    if d == date(2012, 6, 5) and jun04_05_bundle:
        matched_total += amt
        print(f"{d},{amt:.2f},two_day_bundle(part2),{amt:.2f},posted-with-2012-06-04-on-2012-06-05")
        continue

    # CIBC posts Jun 18 + Jun 19 GP funded deposits together on Jun 19.
    # The non-GLOBAL Jun 19 card credits sum to both GP targets exactly.
    if d == date(2012, 6, 18):
        cur.execute(
            """
            SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS c, description
            FROM banking_transactions
            WHERE transaction_date = DATE '2012-06-19'
              AND COALESCE(credit_amount,0) > 0
              AND (
                  UPPER(COALESCE(description,'')) LIKE '%%VCARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%MCARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%ACARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%DCARD%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%CREDIT MEMO%%'
               OR UPPER(COALESCE(description,'')) LIKE '%%GBL%%'
              )
              AND UPPER(COALESCE(description,'')) NOT LIKE '%%GLOBAL SYSTEM%%'
            ORDER BY transaction_id
            """
        )
        bundle_rows = cur.fetchall()
        bundle_sum = sum(r[2] for r in bundle_rows)
        if abs(bundle_sum - (2668.81 + 2808.40)) < 0.005:
            matched_total += amt
            comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in bundle_rows)
            print(f"{d},{amt:.2f},two_day_bundle(part1),{amt:.2f},{comp}")
            jun18_19_bundle = True
            continue

    if d == date(2012, 6, 19) and jun18_19_bundle:
        matched_total += amt
        print(f"{d},{amt:.2f},two_day_bundle(part2),{amt:.2f},posted-with-2012-06-18-on-2012-06-19")
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
        # Return-aware check: credits - debit_return = target
        cur.execute(
            f"""
            SELECT transaction_id, transaction_date, COALESCE(debit_amount,0)::float AS db, description
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s AND %s
              AND COALESCE(debit_amount,0) > 0
              AND (UPPER(COALESCE(description,'')) LIKE '%%VCARD%%'
                OR UPPER(COALESCE(description,'')) LIKE '%%MCARD%%'
                OR UPPER(COALESCE(description,'')) LIKE '%%ACARD%%'
                OR UPPER(COALESCE(description,'')) LIKE '%%DCARD%%'
                OR UPPER(COALESCE(description,'')) LIKE '%%PAYMENT%%'
                OR UPPER(COALESCE(description,'')) LIKE '%%GLOBAL%%')
            ORDER BY transaction_date, transaction_id
            """,
            (d - timedelta(days=1), d + timedelta(days=2)),
        )
        return_rows = cur.fetchall()
        for ret in return_rows:
            adj_target = amt + ret[2]
            crows = [r for r in rows_all if r[2] <= adj_target + 0.005]
            crows.sort(key=lambda r, t=adj_target: abs(t - r[2]))
            crows = crows[:25]
            for n in range(1, 6):
                for combo in itertools.combinations(crows, n):
                    if abs(sum(r[2] for r in combo) - adj_target) < 0.005:
                        matched_total += amt
                        comp = " + ".join(f"{r[0]}:{r[1]}:{r[2]:.2f}:{r[3]}" for r in combo)
                        comp += f" - {ret[0]}:{ret[1]}:{ret[2]:.2f}:{ret[3]}(return)"
                        print(f"{d},{amt:.2f},return_net,{amt:.2f},{comp}")
                        found = True
                        break
                if found:
                    break
            if found:
                break

    if not found:
        print(f"{d},{amt:.2f},unresolved,0.00,")

stmt_total = sum(a for _, a in TARGETS)
print(f"TOTAL,{stmt_total:.2f},matched,{matched_total:.2f},variance,{stmt_total-matched_total:.2f}")

# Fee: Jun 2012 total billed = $1,543.12, debited July 2012
cur.execute(
    """
    SELECT transaction_id, transaction_date, COALESCE(debit_amount,0), description
    FROM banking_transactions
    WHERE transaction_date BETWEEN DATE '2012-07-01' AND DATE '2012-07-10'
      AND COALESCE(debit_amount,0) IN (1543.12, 1516.89, 1096.89)
    ORDER BY transaction_date, transaction_id
    """
)
print("FEE_ROWS")
for r in cur.fetchall():
    print(f"  {r}")

cur.close()
conn.close()

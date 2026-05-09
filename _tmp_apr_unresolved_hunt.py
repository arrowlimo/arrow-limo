from datetime import date, timedelta
import itertools
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
TOP_NEAREST = 25

MERCHANT_KEYWORDS = [
    "MERCH",
    "GLOBAL",
    "VISA",
    "MC",
    "AMEX",
    "CARD",
    "CREDIT",
    "DEPOSIT",
]


def score_desc(text: str) -> int:
    t = (text or "").upper()
    return sum(1 for k in MERCHANT_KEYWORDS if k in t)


def fmt_row(r):
    tid, dt, amt, desc = r
    return f"id={tid} date={dt} amt={amt:.2f} score={score_desc(desc)} desc={desc}"


def find_pair(rows, target):
    # Use cents to avoid float drift.
    cents = [(r, int(round(r[2] * 100))) for r in rows]
    need_map = {}
    t = int(round(target * 100))
    for i, (r, c) in enumerate(cents):
        need = t - c
        if need in need_map:
            j = need_map[need]
            if j != i:
                return cents[j][0], r
        if c not in need_map:
            need_map[c] = i
    return None


db_password = os.environ.get("DB_PASSWORD")
if not db_password:
    raise RuntimeError("Set DB_PASSWORD in environment before running.")

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', os.getenv('NEON_DB_HOST', 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech')),
    port=5432,
    dbname=os.getenv('DB_NAME', os.getenv('NEON_DB_NAME', 'neondb')),
    user=os.getenv('DB_USER', os.getenv('NEON_DB_USER', 'neondb_owner')),
    password=db_password,
)
cur = conn.cursor()

print("APR_UNRESOLVED_CANDIDATE_HUNT")
print("=")

for d, target in TARGETS:
    w_start = d - timedelta(days=WINDOW_BEFORE_DAYS)
    w_end = d + timedelta(days=WINDOW_AFTER_DAYS)

    cur.execute(
        """
        SELECT transaction_id,
               transaction_date,
               COALESCE(credit_amount, 0)::float AS credit,
               COALESCE(description, '')
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount, 0) > 0
        ORDER BY transaction_date, transaction_id
        """,
        (w_start, w_end),
    )
    rows = cur.fetchall()

    rows_by_closeness = sorted(rows, key=lambda r, t=target: abs(t - r[2]))
    nearest = rows_by_closeness[:TOP_NEAREST]

    merchant_like = [r for r in rows if score_desc(r[3]) > 0]
    merchant_like = sorted(merchant_like, key=lambda r, t=target: abs(t - r[2]))[:TOP_NEAREST]

    cur.execute(
        """
        SELECT transaction_id,
               transaction_date,
               COALESCE(credit_amount, 0)::float AS credit,
               COALESCE(description, '')
        FROM banking_transactions
        WHERE transaction_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
          AND ABS(COALESCE(credit_amount,0)::float - %s) < 0.005
        ORDER BY transaction_date, transaction_id
        """,
        (target,),
    )
    exact_year = cur.fetchall()

    pair_any = find_pair(rows, target)
    pair_merch = find_pair([r for r in rows if score_desc(r[3]) > 0], target)

    print(f"\nTARGET date={d} amount={target:.2f} window={w_start}..{w_end}")
    print(f"window_rows={len(rows)} merchant_like_rows={len([r for r in rows if score_desc(r[3]) > 0])}")

    print("exact_amount_anywhere_2012:")
    if exact_year:
        for r in exact_year:
            print("  " + fmt_row(r))
    else:
        print("  none")

    print("pair_candidate_any_desc:")
    if pair_any:
        print("  " + fmt_row(pair_any[0]))
        print("  " + fmt_row(pair_any[1]))
        print(f"  sum={(pair_any[0][2] + pair_any[1][2]):.2f}")
    else:
        print("  none")

    print("pair_candidate_merchant_like:")
    if pair_merch:
        print("  " + fmt_row(pair_merch[0]))
        print("  " + fmt_row(pair_merch[1]))
        print(f"  sum={(pair_merch[0][2] + pair_merch[1][2]):.2f}")
    else:
        print("  none")

    print("nearest_rows:")
    for r in nearest:
        print("  " + fmt_row(r))

    print("nearest_merchant_like_rows:")
    for r in merchant_like:
        print("  " + fmt_row(r))

cur.close()
conn.close()

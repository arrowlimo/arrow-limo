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
MERCHANT_KEYWORDS = ["MERCH","GLOBAL","VISA","MC","AMEX","CARD","CREDIT","DEPOSIT"]

def score_desc(text: str) -> int:
    t = (text or "").upper()
    return sum(1 for k in MERCHANT_KEYWORDS if k in t)

def find_pair(rows, target):
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

pwd = os.environ.get("DB_PASSWORD")
if not pwd:
    raise RuntimeError("DB_PASSWORD not set")
conn = psycopg2.connect(host="localhost",port=5432,dbname="almsdata",user="postgres",password=pwd)
cur = conn.cursor()

for d, target in TARGETS:
    w_start = d - timedelta(days=WINDOW_BEFORE_DAYS)
    w_end = d + timedelta(days=WINDOW_AFTER_DAYS)
    cur.execute("""
        SELECT transaction_id, transaction_date, COALESCE(credit_amount,0)::float AS credit, COALESCE(description,'')
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND COALESCE(credit_amount,0) > 0
        ORDER BY transaction_date, transaction_id
    """, (w_start, w_end))
    rows = cur.fetchall()

    cur.execute("""
        SELECT transaction_date, COALESCE(description,'')
        FROM banking_transactions
        WHERE transaction_date BETWEEN DATE '2012-01-01' AND DATE '2012-12-31'
          AND ABS(COALESCE(credit_amount,0)::float - %s) < 0.005
        ORDER BY transaction_date
    """, (target,))
    exact = cur.fetchall()

    pair_any = find_pair(rows, target)
    pair_merch = find_pair([r for r in rows if score_desc(r[3]) > 0], target)
    nearest3 = sorted(rows, key=lambda r, t=target: abs(t-r[2]))[:3]

    print(f"TARGET {target:.2f} (base {d})")
    if exact:
        details = "; ".join(f"{dt} | {desc}" for dt, desc in exact)
        print(f"  exact_2012: yes -> {details}")
    else:
        print("  exact_2012: no")
    print(f"  pair_any_desc: {'yes' if pair_any else 'no'}")
    print(f"  pair_merchant_like: {'yes' if pair_merch else 'no'}")
    print("  closest3:")
    for _, dt, amt, desc in nearest3:
        print(f"    {dt} | {amt:.2f} | {desc}")

cur.close(); conn.close()

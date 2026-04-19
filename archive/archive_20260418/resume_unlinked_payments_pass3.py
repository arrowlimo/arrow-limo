import csv
import psycopg2

START_DATE = '2015-01-01'
END_DATE = '2026-12-31'
APPLY = True

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

print('=' * 90)
print('RESUME PASS 3: REMAINING UNLINKED PAYMENTS (2015-2026)')
print('=' * 90)

cur.execute(
    """
    SELECT COUNT(*)
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
    """,
    (START_DATE, END_DATE),
)
baseline_unlinked = cur.fetchone()[0]
print(f"Baseline unlinked rows: {baseline_unlinked}")

# Deterministic map A: cp.payment_id -> payments.reserve_number -> charters.reserve_number
cur.execute(
    """
    SELECT cp.id,
           cp.payment_id,
           cp.amount,
           cp.payment_date,
           cp.source,
           p.reserve_number AS mapped_reserve,
           'map_by_payment_id_reserve' AS reason
    FROM charter_payments cp
    JOIN payments p ON p.payment_id = cp.payment_id
    JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE cp.payment_date BETWEEN %s AND %s
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
      AND p.reserve_number IS NOT NULL
      AND p.reserve_number <> ''
    ORDER BY cp.id
    """,
    (START_DATE, END_DATE),
)
map_a = cur.fetchall()

# Deterministic map B: cp.payment_id -> payments.charter_id -> charters.reserve_number
cur.execute(
    """
    SELECT cp.id,
           cp.payment_id,
           cp.amount,
           cp.payment_date,
           cp.source,
           c.reserve_number AS mapped_reserve,
           'map_by_payment_id_charter_id' AS reason
    FROM charter_payments cp
    JOIN payments p ON p.payment_id = cp.payment_id
    JOIN charters c ON c.charter_id = p.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
      AND p.charter_id IS NOT NULL
    ORDER BY cp.id
    """,
    (START_DATE, END_DATE),
)
map_b = cur.fetchall()

# Merge deterministic mappings with priority A over B if same cp.id
merged = {}
for row in map_b:
    merged[row[0]] = row
for row in map_a:
    merged[row[0]] = row

deterministic_rows = [merged[k] for k in sorted(merged.keys())]
print(f"Deterministic remap candidates: {len(deterministic_rows)}")

# Optional review-only unique heuristic (not applied): same date+amount -> single reserve in payments
cur.execute(
    """
    WITH cp_u AS (
      SELECT id, amount, payment_date, source
      FROM charter_payments
      WHERE payment_date BETWEEN %s AND %s
        AND (charter_id IS NULL OR charter_id = '')
    ),
    p_u AS (
      SELECT amount, payment_date, reserve_number
      FROM payments
      WHERE reserve_number IS NOT NULL
        AND reserve_number <> ''
    ),
    matched AS (
      SELECT cp_u.id, cp_u.amount, cp_u.payment_date,
             COUNT(DISTINCT p_u.reserve_number) AS candidate_count,
             MIN(p_u.reserve_number) AS only_reserve
      FROM cp_u
      JOIN p_u ON p_u.amount = cp_u.amount
              AND p_u.payment_date = cp_u.payment_date
      GROUP BY cp_u.id, cp_u.amount, cp_u.payment_date
    )
    SELECT m.id, m.amount, m.payment_date, m.only_reserve
    FROM matched m
    JOIN charters c ON c.reserve_number = m.only_reserve
    WHERE m.candidate_count = 1
    ORDER BY m.id
    """,
    (START_DATE, END_DATE),
)
heuristic_unique = cur.fetchall()
print(f"Unique date+amount heuristic candidates (review only): {len(heuristic_unique)}")

# Export report
report_path = 'l:/limo/resume_pass3_unlinked_review.csv'
with open(report_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['action', 'cp_id', 'payment_id', 'amount', 'payment_date', 'mapped_reserve', 'reason', 'source'])
    for r in deterministic_rows:
        w.writerow(['apply_relink', r[0], r[1], r[2], r[3], r[5], r[6], r[4]])
    for h in heuristic_unique:
        w.writerow(['review_only_unique_amount_date', h[0], '', h[1], h[2], h[3], 'unique_amount_date', ''])
print(f"Exported review file: {report_path}")

if APPLY and deterministic_rows:
    updated = 0
    for r in deterministic_rows:
        cur.execute(
            """
            UPDATE charter_payments
            SET charter_id = %s
            WHERE id = %s
            """,
            (r[5], r[0]),
        )
        updated += cur.rowcount
    conn.commit()
    print(f"Applied deterministic relinks: {updated}")
else:
    print('No deterministic relinks applied.')

# Post-check
cur.execute(
    """
    SELECT COUNT(*)
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
    """,
    (START_DATE, END_DATE),
)
post_unlinked = cur.fetchone()[0]
print(f"Post unlinked rows: {post_unlinked}")

cur.execute(
    """
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE c.charter_id IS NOT NULL) AS matched,
           COUNT(*) FILTER (WHERE c.charter_id IS NULL) AS unmatched
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
    """,
    (START_DATE, END_DATE),
)
print('Post overall (total, matched, unmatched):', cur.fetchone())

cur.close()
conn.close()

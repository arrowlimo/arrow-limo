import csv
import psycopg2

START_DATE = '2015-01-01'
END_DATE = '2026-12-31'

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

print('=' * 90)
print('PASS 7B: REVIEW-ONLY UNIQUE CANDIDATES FOR fix_script')
print('=' * 90)

cur.execute(
    """
    WITH cp_u AS (
      SELECT cp.id, cp.payment_id, cp.client_name, cp.amount, cp.payment_date, cp.payment_method, cp.source
      FROM charter_payments cp
      LEFT JOIN charters c ON c.reserve_number = cp.charter_id
      WHERE cp.payment_date BETWEEN %s AND %s
        AND cp.source = 'fix_script'
        AND c.charter_id IS NULL
        AND (cp.charter_id IS NULL OR cp.charter_id = '')
    ),
    matches AS (
      SELECT cp_u.id, cp_u.payment_id, cp_u.client_name, cp_u.amount, cp_u.payment_date, cp_u.payment_method, cp_u.source,
             COUNT(DISTINCT p.reserve_number) AS candidate_count,
             MIN(p.reserve_number) AS only_reserve
      FROM cp_u
      JOIN payments p ON p.amount = cp_u.amount
                     AND p.payment_date = cp_u.payment_date
      JOIN charters c ON c.reserve_number = p.reserve_number
      WHERE p.reserve_number IS NOT NULL
        AND p.reserve_number <> ''
      GROUP BY cp_u.id, cp_u.payment_id, cp_u.client_name, cp_u.amount, cp_u.payment_date, cp_u.payment_method, cp_u.source
    )
    SELECT id, payment_id, client_name, amount, payment_date, payment_method, source, only_reserve
    FROM matches
    WHERE candidate_count = 1
    ORDER BY payment_date, id
    """,
    (START_DATE, END_DATE),
)
rows = cur.fetchall()
print('unique exact date+amount candidates:', len(rows))

path = 'l:/limo/pass7b_fix_script_unique_review.csv'
with open(path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['cp_id','payment_id','client_name','amount','payment_date','payment_method','source','suggested_reserve'])
    w.writerows(rows)

print('Exported:', path)

cur.close()
conn.close()

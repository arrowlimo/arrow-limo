import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

cur.execute(
    """
    SELECT COUNT(*)
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
    """,
    ('2015-01-01', '2026-12-31'),
)
print('unmatched:', cur.fetchone()[0])

cur.execute(
    """
    SELECT COUNT(*)
    FROM charter_payments cp
    JOIN payments p ON p.payment_id = cp.payment_id
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND p.reserve_number IS NOT NULL
      AND p.reserve_number <> ''
    """,
    ('2015-01-01', '2026-12-31'),
)
print('resolvable_by_payments.payment_id:', cur.fetchone()[0])

cur.execute(
    """
    SELECT cp.id, cp.payment_id, cp.charter_id, p.reserve_number, cp.amount, cp.payment_date, cp.source
    FROM charter_payments cp
    JOIN payments p ON p.payment_id = cp.payment_id
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND p.reserve_number IS NOT NULL
      AND p.reserve_number <> ''
    ORDER BY cp.id
    LIMIT 30
    """,
    ('2015-01-01', '2026-12-31'),
)
print('---sample resolvable via payments---')
for row in cur.fetchall():
    print(row)

cur.execute(
    """
    SELECT cp.id, cp.payment_id, cp.charter_id, cp.amount, cp.payment_date, cp.payment_method, cp.source
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
    ORDER BY cp.id
    LIMIT 30
    """,
    ('2015-01-01', '2026-12-31'),
)
print('---sample remaining unmatched---')
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()

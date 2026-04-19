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
print('SUMMARY: REMAINING UNLINKED PAYMENTS (2015-2026)')
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
print('remaining_unlinked:', cur.fetchone()[0])

print('\nBy source:')
cur.execute(
    """
    SELECT COALESCE(cp.source, '[null]') AS source, COUNT(*) AS cnt, COALESCE(SUM(cp.amount),0) AS amt
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
    GROUP BY COALESCE(cp.source, '[null]')
    ORDER BY cnt DESC
    """,
    (START_DATE, END_DATE),
)
rows = cur.fetchall()
for r in rows:
    print(r)

print('\nBy payment_method:')
cur.execute(
    """
    SELECT COALESCE(cp.payment_method, '[null]') AS method, COUNT(*) AS cnt, COALESCE(SUM(cp.amount),0) AS amt
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
    GROUP BY COALESCE(cp.payment_method, '[null]')
    ORDER BY cnt DESC
    """,
    (START_DATE, END_DATE),
)
for r in cur.fetchall():
    print(r)

# Export full remaining list
cur.execute(
    """
    SELECT cp.id, cp.payment_id, cp.charter_id, cp.amount, cp.payment_date, cp.payment_method, cp.source, cp.client_name
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
      AND (cp.charter_id IS NULL OR cp.charter_id = '')
    ORDER BY cp.payment_date, cp.id
    """,
    (START_DATE, END_DATE),
)
remaining = cur.fetchall()

path = 'l:/limo/remaining_unlinked_payments_2015_2026.csv'
with open(path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['id', 'payment_id', 'charter_id', 'amount', 'payment_date', 'payment_method', 'source', 'client_name'])
    w.writerows(remaining)

print(f"\nExported: {path}")

cur.close()
conn.close()

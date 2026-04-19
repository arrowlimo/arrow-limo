import psycopg2

START_DATE = '2012-01-01'
END_DATE = '2014-12-31'

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

print('=' * 90)
print('DEEP DIVE LINK RESOLUTION (2012-2014)')
print('=' * 90)

# Unmatched by reserve_number
cur.execute(
    """
    SELECT cp.id, cp.payment_id, cp.charter_id, cp.amount, cp.payment_date, cp.payment_method, cp.source
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
    ORDER BY cp.id
    """,
    (START_DATE, END_DATE),
)
unmatched = cur.fetchall()
print(f"Unmatched rows by reserve_number: {len(unmatched)}")

print('\nAttempt resolution by matching cp.charter_id to charters.charter_id...')
resolved = []
unresolved = []
for r in unmatched:
    cp_id, payment_id, cp_charter_id, amount, payment_date, method, source = r
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, status
        FROM charters
        WHERE CAST(charter_id AS VARCHAR) = %s
        """,
        (cp_charter_id,),
    )
    hits = cur.fetchall()
    if len(hits) == 1:
        resolved.append((r, hits[0]))
    else:
        unresolved.append((r, hits))

print(f"Resolvable via charter_id->reserve_number: {len(resolved)}")
print(f"Still unresolved: {len(unresolved)}")

print('\nResolved mappings:')
for (r, h) in resolved:
    print(
        f"cp.id={r[0]} cp.charter_id={r[2]} -> reserve={h[1]} "
        f"(charter_id={h[0]}, charter_date={h[2]})"
    )

print('\nUnresolved rows:')
for (r, hits) in unresolved:
    print(f"cp.id={r[0]} cp.charter_id={r[2]} hits={len(hits)}")

# Duplicate payment_id rows details
cur.execute(
    """
    SELECT payment_id
    FROM charter_payments
    WHERE payment_date BETWEEN %s AND %s
      AND payment_id IS NOT NULL
    GROUP BY payment_id
    HAVING COUNT(*) > 1
    ORDER BY payment_id
    """,
    (START_DATE, END_DATE),
)
dup_payment_ids = [x[0] for x in cur.fetchall()]
print(f"\nDuplicate payment_id groups: {dup_payment_ids}")

for pid in dup_payment_ids:
    print(f"\nRows for payment_id={pid}:")
    cur.execute(
        """
        SELECT id, payment_id, charter_id, amount, payment_date, payment_method, source, imported_at
        FROM charter_payments
        WHERE payment_id = %s
        ORDER BY imported_at NULLS LAST, id
        """,
        (pid,),
    )
    rows = cur.fetchall()
    for row in rows:
        print(row)

cur.close()
conn.close()

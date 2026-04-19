from decimal import Decimal
import csv
import psycopg2

START_DATE = '2012-01-01'
END_DATE = '2014-12-31'
APPLY_UNLINK = False

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()


def q2(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'))


print('=' * 88)
print('DEEP DIVE PAYMENT LINK AUDIT (2012-2014)')
print('=' * 88)

# Schema safety check
cur.execute(
    """
    SELECT column_name, is_nullable, data_type
    FROM information_schema.columns
    WHERE table_name = 'charter_payments'
    ORDER BY ordinal_position
    """
)
cols = cur.fetchall()
charter_id_meta = [r for r in cols if r[0] == 'charter_id'][0]
print(f"charter_payments.charter_id nullable={charter_id_meta[1]} type={charter_id_meta[2]}")

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

total, matched, unmatched = cur.fetchone()
print(f"Payments in range: total={total}, matched={matched}, unmatched={unmatched}")

# Identify duplicates by payment_id (same source payment imported multiple times)
cur.execute(
    """
    SELECT payment_id, COUNT(*) AS c, COALESCE(SUM(amount), 0) AS amt
    FROM charter_payments
    WHERE payment_date BETWEEN %s AND %s
      AND payment_id IS NOT NULL
    GROUP BY payment_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, payment_id
    """,
    (START_DATE, END_DATE),
)
payment_id_dups = cur.fetchall()
print(f"Duplicate payment_id groups: {len(payment_id_dups)}")

# Build duplicate row candidates keeping earliest row for each payment_id and unlinking the rest.
cur.execute(
    """
    WITH ranked AS (
      SELECT id, payment_id, charter_id, amount, payment_date, payment_method, source,
             ROW_NUMBER() OVER (
               PARTITION BY payment_id
               ORDER BY imported_at NULLS LAST, id
             ) AS rn
      FROM charter_payments
      WHERE payment_date BETWEEN %s AND %s
        AND payment_id IS NOT NULL
    )
    SELECT id, payment_id, charter_id, amount, payment_date, payment_method, source
    FROM ranked
    WHERE rn > 1
    ORDER BY payment_id, id
    """,
    (START_DATE, END_DATE),
)
duplicate_rows_to_unlink = cur.fetchall()

# Unmatched link candidates (charter_id value does not match any reserve_number)
cur.execute(
    """
    SELECT cp.id, cp.payment_id, cp.charter_id, cp.amount, cp.payment_date, cp.payment_method, cp.source
    FROM charter_payments cp
    LEFT JOIN charters c ON c.reserve_number = cp.charter_id
    WHERE cp.payment_date BETWEEN %s AND %s
      AND c.charter_id IS NULL
    ORDER BY cp.payment_date, cp.id
    """,
    (START_DATE, END_DATE),
)
unmatched_rows = cur.fetchall()

# Union IDs to unlink
dup_ids = {r[0] for r in duplicate_rows_to_unlink}
unmatched_ids = {r[0] for r in unmatched_rows}
all_unlink_ids = sorted(dup_ids | unmatched_ids)

print(f"Rows to unlink for duplicates: {len(duplicate_rows_to_unlink)}")
print(f"Rows to unlink for unmatched reserve links: {len(unmatched_rows)}")
print(f"Total unique rows to unlink: {len(all_unlink_ids)}")

# Export review CSV
csv_path = 'l:/limo/payment_unlink_candidates_2012_2014.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow([
        'id', 'reason', 'payment_id', 'charter_id', 'amount',
        'payment_date', 'payment_method', 'source'
    ])
    for r in duplicate_rows_to_unlink:
        w.writerow([r[0], 'duplicate_payment_id', r[1], r[2], q2(r[3]), r[4], r[5], r[6]])
    for r in unmatched_rows:
        reason = 'unmatched_reserve' if r[0] not in dup_ids else 'duplicate_and_unmatched'
        w.writerow([r[0], reason, r[1], r[2], q2(r[3]), r[4], r[5], r[6]])

print(f"Exported candidate list: {csv_path}")

if APPLY_UNLINK and all_unlink_ids:
    cur.execute(
        """
        UPDATE charter_payments
        SET charter_id = NULL
        WHERE id = ANY(%s)
        """,
        (all_unlink_ids,),
    )
    print(f"Unlinked rows updated: {cur.rowcount}")
    conn.commit()
    print('Changes committed.')
else:
    print('DRY RUN ONLY: no database changes applied.')

# Show top examples
print('\nSample duplicate unlink candidates (first 20):')
for r in duplicate_rows_to_unlink[:20]:
    print(r)

print('\nSample unmatched unlink candidates (first 20):')
for r in unmatched_rows[:20]:
    print(r)

cur.close()
conn.close()

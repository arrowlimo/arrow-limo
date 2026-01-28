import psycopg2
from datetime import datetime

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

RESERVE = '016086'
AMOUNT = 1983.84
DATE = datetime(2022,7,6)

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Get charter_id for reserve
cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (RESERVE,))
row = cur.fetchone()
if not row:
    print(f"✗ No charter found for reserve {RESERVE}")
    conn.close()
    raise SystemExit(1)
charter_id = row[0]
print(f"Charter {charter_id} found for reserve {RESERVE}")

# Find candidate unlinked row(s)
cur.execute(
    """
    SELECT id, refund_date, amount, source_file
    FROM charter_refunds
    WHERE charter_id IS NULL
      AND reserve_number IS NULL
      AND ABS(amount - %s) < 0.01
      AND refund_date = %s
    ORDER BY id
    """,
    (AMOUNT, DATE)
)
rows = cur.fetchall()
print(f"Unlinked rows matching amount/date: {len(rows)}")
if len(rows) != 1:
    for r in rows:
        print("  -", r)
    print("✗ Aborting to avoid incorrect update.")
    conn.close()
    raise SystemExit(2)

rid = rows[0][0]
cur.execute(
    """
    UPDATE charter_refunds
       SET reserve_number = %s, charter_id = %s
     WHERE id = %s
    """,
    (RESERVE, charter_id, rid)
)
print(f"✓ Updated charter_refunds #{rid} -> reserve {RESERVE}, charter_id {charter_id}")
conn.commit()
conn.close()
print("Done.")

"""
Apply manual refund linkages based on evidence (email/Square/LMS).

This script links the $91.88 refund (2016-07) to reserve_number 012567.
Safety: updates only when a single unlinked row matches amount/date window.
"""

import psycopg2
from datetime import datetime, timedelta

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

RESERVE = '012567'
AMOUNT = 91.88
START = datetime(2016, 6, 30)
END = datetime(2016, 7, 10)

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Find charter by reserve_number
cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (RESERVE,))
row = cur.fetchone()
if not row:
    print(f"✗ No charter found for reserve {RESERVE}")
    conn.close()
    raise SystemExit(1)
charter_id = row[0]
print(f"Charter {charter_id} found for reserve {RESERVE}")

# Find matching unlinked refund(s)
cur.execute(
    """
    SELECT id, refund_date, amount, description
    FROM charter_refunds
    WHERE reserve_number IS NULL
      AND reserve_number IS NULL
      AND ABS(amount - %s) < 0.01
      AND refund_date BETWEEN %s AND %s
    ORDER BY refund_date
    """,
    (AMOUNT, START, END)
)
matches = cur.fetchall()
print(f"Unlinked refunds matching $ {AMOUNT:.2f} in window: {len(matches)}")

if len(matches) != 1:
    print("✗ Aborting: expected exactly 1 match to update.")
    for m in matches:
        print(f"  - ID {m[0]} date {m[1]} amount {m[2]} desc {(m[3] or '')[:60]}")
    conn.close()
    raise SystemExit(2)

refund_id = matches[0][0]

# Apply update
cur.execute(
    """
    UPDATE charter_refunds
       SET reserve_number = %s,
           charter_id = %s
     WHERE id = %s
    """,
    (RESERVE, charter_id, refund_id)
)
print(f"✓ Updated charter_refunds #{refund_id} -> reserve {RESERVE}, charter_id {charter_id}")

conn.commit()
conn.close()
print("Done.")

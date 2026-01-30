"""
Quick verifier for specific refunds:
- $91.88 around 2016-07 should be linked to reserve 012567
- $1,983.84 around 2022-07-06 should be linked to reserve 016086
"""

import psycopg2
from datetime import datetime

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

checks = [
    {"amount": 91.88, "reserve": "012567", "start": datetime(2016,6,30), "end": datetime(2016,7,10)},
    {"amount": 1983.84, "reserve": "016086", "start": datetime(2022,7,1), "end": datetime(2022,7,12)},
]

conn = psycopg2.connect(**DB)
cur = conn.cursor()

for c in checks:
    cur.execute(
        """
        SELECT id, refund_date, amount, reserve_number, charter_id, source_file
        FROM charter_refunds
        WHERE ABS(amount - %s) < 0.01
          AND refund_date BETWEEN %s AND %s
        ORDER BY refund_date
        """,
        (c["amount"], c["start"], c["end"])
    )
    rows = cur.fetchall()
    print(f"\nAmount ${c['amount']:.2f} between {c['start'].date()} and {c['end'].date()} - expected reserve {c['reserve']}")
    if not rows:
        print("  ✗ No rows found")
        continue
    for r in rows:
        rid, rdate, amt, rsv, cid, src = r
        linked = "yes" if cid else "no"
        ok = (rsv == c["reserve"]) and (cid is not None)
        print(f"  • id={rid} date={rdate} reserve={rsv} charter_id={cid} src={src} linked={linked} {'✓ OK' if ok else '✗ needs link'}")

conn.close()
print("\nDone.")

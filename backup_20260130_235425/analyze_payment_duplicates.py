#!/usr/bin/env python
import os
import psycopg2
from collections import defaultdict
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REDACTED***"

KEYS = [
    ("reserve_number",),
    ("reserve_number","amount","payment_date"),
    ("reserve_number","amount","payment_date","payment_method"),
    ("amount","payment_date","payment_method"),
]


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute("SELECT reserve_number, amount, payment_date, payment_method FROM payments")
    rows = cur.fetchall()
    print(f"Total payments: {len(rows)}")

    for key in KEYS:
        groups = defaultdict(list)
        for r in rows:
            record = {
                "reserve_number": r[0],
                "amount": float(r[1]) if r[1] is not None else 0.0,
                "payment_date": str(r[2]) if r[2] is not None else None,
                "payment_method": r[3],
            }
            k = tuple(record.get(f) for f in key)
            groups[k].append(record)
        dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"\nDuplicate groups by {key}: {len(dup_groups)}")
        # Show top 10 examples
        count = 0
        for k, v in list(dup_groups.items())[:10]:
            print(f"  Key={k} -> {len(v)} rows")
        if not dup_groups:
            print("  None detected")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()

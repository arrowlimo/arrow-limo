#!/usr/bin/env python3
"""
Check whether a given value (e.g., 007130) exists as a reserve_number in charters
and/or in payments.reserve_number. Handles leading zeros by comparing as text and
LPAD to 6 digits.
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

VALUE = sys.argv[1] if len(sys.argv) > 1 else '007130'

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )

def main():
    val = VALUE.strip()
    val_no_zeros = val.lstrip('0') or '0'
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print(f"=== Lookup reserve_number: '{val}' (also checking '{val_no_zeros}') ===")

    # Charters check
    cur.execute(
        f"""
        SELECT charter_id, reserve_number, charter_date, client_id, status
        FROM charters
        WHERE (
            reserve_number::text = %s
            OR reserve_number::text = %s
            OR LPAD(reserve_number::text, 6, '0') = %s
        )
        ORDER BY charter_date, charter_id
        """,
        (val, val_no_zeros, val)
    )
    rows = cur.fetchall()
    if rows:
        print(f"Found in charters: {len(rows)} row(s)")
        for r in rows[:10]:
            print(dict(r))
    else:
        print("Not found in charters.")

    # Payments check
    cur.execute(
        f"""
        SELECT payment_id, reserve_number, payment_date, amount, payment_method
        FROM payments
        WHERE (
            reserve_number::text = %s
            OR reserve_number::text = %s
            OR LPAD(reserve_number::text, 6, '0') = %s
        )
        ORDER BY payment_date, payment_id
        """,
        (val, val_no_zeros, val)
    )
    rows = cur.fetchall()
    if rows:
        print(f"Found in payments: {len(rows)} row(s)")
        for r in rows[:10]:
            print(dict(r))
    else:
        print("Not found in payments.")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()

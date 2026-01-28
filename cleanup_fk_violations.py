"""
Cleanup script to resolve FK violations prior to adding constraints.
Default is DRY_RUN (no writes). Toggle DRY_RUN=False to apply changes.

Actions:
1) payments: null reserve_number for vendor/employee/chargeback pseudo-keys.
2) receipts: null reserve_number for a small orphan set.
3) charter_charges: null reserve_number for orphan reserve_numbers.
4) charter_payments: null payment_id when missing in payments; null charter_id when
   numeric but missing in charters.
"""

import psycopg2
from psycopg2.extras import execute_values

DB = dict(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
DRY_RUN = False  # set to False to apply updates

# Patterns to null in payments.reserve_number
PAYMENT_NULL_PATTERNS = ["VENDOR_%", "EMP_%", "CHARGEBACK_%"]

# Specific reserve_numbers to null in receipts and charter_charges
RECEIPT_ORPHANS = ["019787", "019794", "019781", "019783", "019791", "019798", "019808"]
CHARGE_ORPHANS = ["015968", "005558", "008290", "008308", "015982", "016023", "018692"]

# Remaining LARGE_PAY placeholders to null in payments.reserve_number
PAYMENT_LARGE_PAY = [
    "LARGE_PAY_25646", "LARGE_PAY_25658", "LARGE_PAY_25661", "LARGE_PAY_38693",
    "LARGE_PAY_42285", "LARGE_PAY_42292", "LARGE_PAY_49713", "LARGE_PAY_49733",
    "LARGE_PAY_49734", "LARGE_PAY_49735", "LARGE_PAY_49736", "LARGE_PAY_49745",
    "LARGE_PAY_62767", "LARGE_PAY_62770", "LARGE_PAY_62780", "LARGE_PAY_79782",
    "LARGE_PAY_81345", "LARGE_PAY_81346", "LARGE_PAY_81782", "LARGE_PAY_81948",
    "LARGE_PAY_88527", "LARGE_PAY_88534", "LARGE_PAY_88550", "LARGE_PAY_90579",
]


def summarize(cur, label, sql, params=None):
    cur.execute(sql, params or [])
    count = cur.fetchone()[0]
    print(f"{label}: {count}")
    return count


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    print(f"DRY_RUN={DRY_RUN}")

    # 1) payments pseudo-keys
    pattern_clause = " OR ".join(["p.reserve_number ILIKE %s" for _ in PAYMENT_NULL_PATTERNS])
    sql = f"SELECT COUNT(*) FROM payments p WHERE {pattern_clause}"
    before = summarize(cur, "payments pseudo-key rows", sql, PAYMENT_NULL_PATTERNS)
    if not DRY_RUN and before:
        pattern_clause = " OR ".join(["reserve_number ILIKE %s" for _ in PAYMENT_NULL_PATTERNS])
        cur.execute(
            f"UPDATE payments SET reserve_number = NULL WHERE {pattern_clause}",
            PAYMENT_NULL_PATTERNS,
        )
        print(f"payments updated: {cur.rowcount}")

    # payments LARGE_PAY placeholders
    before = summarize(cur, "payments LARGE_PAY placeholders", """
        SELECT COUNT(*) FROM payments p WHERE p.reserve_number = ANY(%s)
    """, (PAYMENT_LARGE_PAY,))
    if not DRY_RUN and before:
        cur.execute(
            """
            UPDATE payments
            SET reserve_number = NULL
            WHERE reserve_number = ANY(%s)
            """,
            (PAYMENT_LARGE_PAY,),
        )
        print(f"payments LARGE_PAY updated: {cur.rowcount}")

    # 2) receipts orphan reserve_numbers
    before = summarize(cur, "receipts orphan reserve_numbers", """
        SELECT COUNT(*) FROM receipts r WHERE r.reserve_number = ANY(%s)
    """, (RECEIPT_ORPHANS,))
    if not DRY_RUN and before:
        cur.execute(
            """
            UPDATE receipts
            SET reserve_number = NULL
            WHERE reserve_number = ANY(%s)
            """,
            (RECEIPT_ORPHANS,),
        )
        print(f"receipts updated: {cur.rowcount}")

    # 3) charter_charges orphan reserve_numbers
    before = summarize(cur, "charter_charges orphan reserve_numbers", """
        SELECT COUNT(*) FROM charter_charges cc WHERE cc.reserve_number = ANY(%s)
    """, (CHARGE_ORPHANS,))
    if not DRY_RUN and before:
        cur.execute(
            """
            UPDATE charter_charges
            SET reserve_number = NULL
            WHERE reserve_number = ANY(%s)
            """,
            (CHARGE_ORPHANS,),
        )
        print(f"charter_charges updated: {cur.rowcount}")

    # 4a) charter_payments payment_id missing in payments -> null it
    before = summarize(cur, "charter_payments payment_id missing in payments", """
        SELECT COUNT(*)
        FROM charter_payments cp
        WHERE cp.payment_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.payment_id = cp.payment_id)
    """)
    if not DRY_RUN and before:
        cur.execute(
            """
            UPDATE charter_payments cp
            SET payment_id = NULL
            WHERE cp.payment_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.payment_id = cp.payment_id)
            """
        )
        print(f"charter_payments payment_id nulled: {cur.rowcount}")

    # 4b) charter_payments charter_id numeric missing in charters -> null it
    before = summarize(cur, "charter_payments numeric charter_id missing in charters", """
        SELECT COUNT(*)
        FROM charter_payments cp
        WHERE cp.reserve_number IS NOT NULL
          AND cp.charter_id ~ '^[0-9]+$'
          AND NOT EXISTS (SELECT 1 FROM charters c WHERE c.charter_id = cp.charter_id::integer)
    """)
    if not DRY_RUN and before:
        cur.execute(
            """
            UPDATE charter_payments cp
            SET charter_id = NULL
            WHERE cp.reserve_number IS NOT NULL
              AND cp.charter_id ~ '^[0-9]+$'
              AND NOT EXISTS (SELECT 1 FROM charters c WHERE c.charter_id = cp.charter_id::integer)
            """
        )
        print(f"charter_payments charter_id nulled: {cur.rowcount}")

    if DRY_RUN:
        print("DRY RUN ONLY - no changes written.")
        conn.rollback()
    else:
        conn.commit()
        print("Committed changes.")
    conn.close()


if __name__ == "__main__":
    main()

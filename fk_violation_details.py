"""Detail FK violation keys to prioritize fixes before adding constraints."""
import psycopg2
from textwrap import indent

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

QUERIES = [
    (
        "payments.reserve_number missing in charters",
        """
        SELECT p.reserve_number, COUNT(*) AS cnt
        FROM payments p
        WHERE p.reserve_number IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
          )
        GROUP BY p.reserve_number
        ORDER BY cnt DESC, p.reserve_number
        LIMIT 25;
        """,
    ),
    (
        "receipts.reserve_number missing in charters",
        """
        SELECT r.reserve_number, COUNT(*) AS cnt
        FROM receipts r
        WHERE r.reserve_number IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = r.reserve_number
          )
        GROUP BY r.reserve_number
        ORDER BY cnt DESC, r.reserve_number
        LIMIT 25;
        """,
    ),
    (
        "charter_charges.reserve_number missing in charters",
        """
        SELECT cc.reserve_number, COUNT(*) AS cnt
        FROM charter_charges cc
        WHERE cc.reserve_number IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = cc.reserve_number
          )
        GROUP BY cc.reserve_number
        ORDER BY cnt DESC, cc.reserve_number
        LIMIT 25;
        """,
    ),
    (
        "charter_payments.payment_id missing in payments",
        """
        SELECT cp.payment_id, COUNT(*) AS cnt
        FROM charter_payments cp
        WHERE cp.payment_id IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.payment_id = cp.payment_id
          )
        GROUP BY cp.payment_id
        ORDER BY cnt DESC, cp.payment_id
        LIMIT 25;
        """,
    ),
    (
        "charter_payments.charter_id (numeric) missing in charters",
        """
        SELECT cp.charter_id, COUNT(*) AS cnt
        FROM charter_payments cp
        WHERE cp.reserve_number IS NOT NULL
          AND cp.charter_id ~ '^[0-9]+$'
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.charter_id = cp.charter_id::integer
          )
        GROUP BY cp.charter_id
        ORDER BY cnt DESC, cp.charter_id
        LIMIT 25;
        """,
    ),
]


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    for title, sql in QUERIES:
        print("=" * 80)
        print(title)
        print("-" * 80)
        cur.execute(sql)
        rows = cur.fetchall()
        if not rows:
            print("(none)")
        else:
            for key, cnt in rows:
                print(f"{key}\t{cnt}")
        print()
    conn.close()


if __name__ == "__main__":
    main()

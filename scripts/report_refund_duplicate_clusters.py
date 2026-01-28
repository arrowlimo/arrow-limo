#!/usr/bin/env python3
"""
Report duplicate clusters in charter_refunds: same refund_date (day) and same amount.
Lists clusters with count > 1, and prints each row details for manual review.
Optionally limit to a year or a minimum amount via args.
"""
import argparse
import os
import psycopg2


def get_pg():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        database=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REMOVED***')
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-amount', type=float, default=0.0, help='Minimum refund amount to include')
    ap.add_argument('--year', type=int, help='Filter by refund year')
    args = ap.parse_args()

    pg = get_pg()
    cur = pg.cursor()

    where = ["amount >= %s"]
    params = [args.min_amount]
    if args.year:
        where.append("EXTRACT(YEAR FROM refund_date) = %s")
        params.append(args.year)

    where_clause = " AND ".join(where)

    cur.execute(
        f"""
        WITH clusters AS (
            SELECT refund_date::date AS day, amount, COUNT(*) AS cnt
            FROM charter_refunds
            WHERE {where_clause}
            GROUP BY 1,2
            HAVING COUNT(*) > 1
            ORDER BY day, amount DESC
        )
        SELECT c.day, c.amount, c.cnt,
               cr.id, cr.reserve_number, cr.charter_id, cr.description
        FROM clusters c
        JOIN charter_refunds cr
          ON cr.refund_date::date = c.day AND ABS(cr.amount - c.amount) < 0.01
        ORDER BY c.day, c.amount DESC, cr.id
        """,
        params
    )

    rows = cur.fetchall()
    if not rows:
        print("No duplicate clusters found for the given filters.")
        return

    print("Duplicate clusters (same day + same amount):")
    print("="*90)
    current = None
    count_cluster = 0
    for day, amount, cnt, rid, reserve, charter_id, desc in rows:
        key = (day, float(amount))
        if current != key:
            if current is not None:
                print()
            print(f"{day} | ${float(amount):,.2f} | occurrences: {cnt}")
            print("-"*90)
            current = key
            count_cluster += 1
        print(f"  id={rid:>5} reserve={reserve or 'NULL':>8} charter_id={str(charter_id) if charter_id else 'NULL':>8} desc={desc[:80] if desc else ''}")

    print("\nTotal clusters:", count_cluster)
    cur.close(); pg.close()

if __name__ == '__main__':
    main()

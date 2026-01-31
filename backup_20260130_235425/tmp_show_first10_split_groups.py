#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

cur.execute(
    """
    WITH parents AS (
        SELECT p.receipt_id AS parent_id, p.receipt_date, p.vendor_name, p.split_group_total
        FROM receipts p
        WHERE p.parent_receipt_id IS NULL
          AND p.is_split_receipt = TRUE
          AND EXTRACT(YEAR FROM p.receipt_date) = 2019
        ORDER BY p.receipt_date, p.receipt_id
        LIMIT 10
    )
    SELECT parent_id FROM parents
    """
)
parent_ids = [r[0] for r in cur.fetchall()]
print("First 10 parent_ids by date:", parent_ids)
print("\nRows (role, receipt_id, parent_receipt_id, vendor, amount, split_total):")

if parent_ids:
    cur.execute(
        """
        SELECT
            CASE WHEN r.receipt_id = p.receipt_id THEN 'PARENT' ELSE 'CHILD' END AS role,
            r.receipt_id,
            r.parent_receipt_id,
            r.vendor_name,
            r.gross_amount,
            p.split_group_total,
            r.receipt_date
        FROM receipts r
        JOIN receipts p ON p.receipt_id = COALESCE(r.parent_receipt_id, r.receipt_id)
        WHERE p.receipt_id = ANY(%s)
        ORDER BY p.receipt_date, p.receipt_id, role DESC, r.receipt_id
        """,
        (parent_ids,),
    )
    rows = cur.fetchall()
    for role, rid, prid, vend, amt, st, dt in rows:
        print(f"{dt} | {vend} | {role:<6} | receipt_id={rid} | parent_id={prid} | amount={amt} | split_total={st}")

cur.close()
conn.close()

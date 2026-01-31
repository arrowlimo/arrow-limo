#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()
cur.execute("""
SELECT p.receipt_id AS parent_id,
       p.receipt_date,
       p.vendor_name,
       p.split_group_total,
       p.gross_amount AS parent_amount,
       SUM(c.gross_amount) AS child_total,
       (p.gross_amount + COALESCE(SUM(c.gross_amount),0)) AS combined_total,
       (p.gross_amount + COALESCE(SUM(c.gross_amount),0)) - p.split_group_total AS diff
FROM receipts p
LEFT JOIN receipts c ON c.parent_receipt_id = p.receipt_id
WHERE p.is_split_receipt = TRUE
  AND p.parent_receipt_id IS NULL
  AND EXTRACT(YEAR FROM p.receipt_date) = 2019
GROUP BY p.receipt_id, p.receipt_date, p.vendor_name, p.split_group_total, p.gross_amount
HAVING ABS((p.gross_amount + COALESCE(SUM(c.gross_amount),0)) - p.split_group_total) > 0.009
ORDER BY p.receipt_date, p.receipt_id;
""")
rows=cur.fetchall()
print("ParentID | Date | Vendor | SplitTotal | Parent | ChildTotal | Combined | Diff")
for r in rows:
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]:.2f} | {r[4]:.2f} | {(r[5] or 0):.2f} | {r[6]:.2f} | {r[7]:+.2f}")
cur.close();conn.close()

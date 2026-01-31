#!/usr/bin/env python3
"""
Analyze 2019 split groups: do descriptions explain the split reason (full split vs partial cash)?
"""
import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

print("2019 SPLIT GROUPS - Description/Notes Analysis")
print("=" * 150)
print(f"{'Parent ID':<10} {'Date':<12} {'Vendor':<25} {'Split Total':<12} {'Banking Link':<12} {'Description/Notes':<60}")
print("-" * 150)

cur.execute(
    """
    SELECT p.receipt_id, p.receipt_date, p.vendor_name, p.split_group_total, 
           p.banking_transaction_id, p.description
    FROM receipts p
    WHERE p.is_split_receipt = TRUE
      AND p.parent_receipt_id IS NULL
      AND EXTRACT(YEAR FROM p.receipt_date) = 2019
    ORDER BY p.receipt_date, p.receipt_id
    """
)

groups = cur.fetchall()

for parent_id, date, vendor, split_total, banking_id, description in groups:
    banking_str = "YES" if banking_id else "NO"
    desc_str = (description or "")[:60] if description else ""
    print(f"{parent_id:<10} {date} {vendor:<25} {split_total:<12.2f} {banking_str:<12} {desc_str:<60}")

print("\n" + "=" * 150)
print("CHILD RECEIPTS - Check if descriptions note split reason")
print("=" * 150)
print(f"{'Child ID':<10} {'Parent ID':<10} {'Vendor':<25} {'Amount':<12} {'Description/Notes':<60}")
print("-" * 150)

cur.execute(
    """
    SELECT c.receipt_id, c.parent_receipt_id, c.vendor_name, c.gross_amount, c.description
    FROM receipts c
    WHERE c.parent_receipt_id IS NOT NULL
      AND EXTRACT(YEAR FROM c.receipt_date) = 2019
      AND c.is_split_receipt = TRUE
    ORDER BY c.parent_receipt_id, c.receipt_id
    LIMIT 30
    """
)

for child_id, parent_id, vendor, amount, description in cur.fetchall():
    desc_str = (description or "")[:60] if description else ""
    print(f"{child_id:<10} {parent_id:<10} {vendor:<25} {amount:<12.2f} {desc_str:<60}")

print("\n" + "=" * 150)
print("ANALYSIS")
print("=" * 150)
print("""
Looking for patterns in descriptions that explain the split:
  - "SPLIT/" prefix = already marked as split
  - "CASH" = partial cash payment
  - "DRIVER" = driver reimbursement
  - "CREDIT" = gas station credit
  - Category names (FUEL, FOOD, PERSONAL) = category split
  
This will help determine if banking link should be on parent or distributed across children.
""")

cur.close()
conn.close()

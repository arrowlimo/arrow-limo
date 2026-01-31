#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

# Get all 2019 split groups
cur.execute(
    """
    SELECT DISTINCT p.receipt_id as parent_id, p.receipt_date, p.vendor_name, 
           p.split_group_total, p.banking_transaction_id,
           SUM(COALESCE(r.gross_amount, 0)) OVER (PARTITION BY COALESCE(r.parent_receipt_id, r.receipt_id)) as component_sum
    FROM receipts p
    LEFT JOIN receipts r ON r.parent_receipt_id = p.receipt_id OR r.receipt_id = p.receipt_id
    WHERE p.is_split_receipt = TRUE
      AND p.parent_receipt_id IS NULL
      AND EXTRACT(YEAR FROM p.receipt_date) = 2019
    ORDER BY p.receipt_date, p.receipt_id
    """
)

groups = cur.fetchall()
print("2019 SPLIT GROUPS - Banking Link Analysis")
print("=" * 120)
print(f"{'Date':<12} {'Vendor':<30} {'Parent ID':<10} {'Split Total':<12} {'Component Sum':<12} {'Banking ID':<10}")
print("-" * 120)

for parent_id, date, vendor, split_total, banking_id, comp_sum in groups:
    banking_str = str(banking_id) if banking_id else "NULL"
    print(f"{date} {vendor:<30} {parent_id:<10} {split_total:<12.2f} {comp_sum:<12.2f} {banking_str:<10}")

# Now check if banking_transaction_id exists and matches amount
print("\n" + "=" * 120)
print("Banking Transaction Details (where linked)")
print("=" * 120)

cur.execute(
    """
    SELECT DISTINCT p.receipt_id, p.receipt_date, p.vendor_name, p.split_group_total, 
           p.banking_transaction_id
    FROM receipts p
    WHERE p.is_split_receipt = TRUE
      AND p.parent_receipt_id IS NULL
      AND EXTRACT(YEAR FROM p.receipt_date) = 2019
      AND p.banking_transaction_id IS NOT NULL
    ORDER BY p.receipt_date, p.receipt_id
    """
)

linked_groups = cur.fetchall()
print(f"\nFound {len(linked_groups)} parent receipts with banking links:\n")
print(f"{'Parent ID':<10} {'Date':<12} {'Vendor':<30} {'Split Total':<12} {'Banking ID':<10}")
print("-" * 120)

for parent_id, date, vendor, split_total, banking_id in linked_groups:
    print(f"{parent_id:<10} {date} {vendor:<30} {split_total:<12.2f} {banking_id:<10}")
    
    # Get banking transaction details
    cur.execute(
        "SELECT description, debit_amount, credit_amount FROM banking_transactions WHERE transaction_id = %s",
        (banking_id,)
    )
    bt_row = cur.fetchone()
    if bt_row:
        bt_desc, bt_debit, bt_credit = bt_row
        bt_amount = float(bt_debit or 0) + float(bt_credit or 0)
        match = "✓" if abs(bt_amount - float(split_total)) < 0.01 else "✗"
        print(f"  {match} Banking: {bt_desc[:50]} | Amount: {bt_amount}")
        if abs(bt_amount - float(split_total)) >= 0.01:
            print(f"     MISMATCH: Banking ${bt_amount} vs Split Total ${split_total}")

cur.close()
conn.close()

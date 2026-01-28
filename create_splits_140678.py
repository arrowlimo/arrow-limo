"""
Create test splits for receipt #140678
Vehicle Maintenance $28.05 (GL 6900) + Driver Meal $30.19 (GL 6500) = $58.24
"""
import os
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

try:
    # Get original receipt
    cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, payment_method, 
           gl_account_code, description
    FROM receipts 
    WHERE receipt_id = 140678
    """)
    original = cur.fetchone()
    if not original:
        print("Receipt 140678 not found!")
        conn.close()
        exit(1)
    
    receipt_id, receipt_date, vendor_name, gross_amount, payment_method, gl_code, desc = original
    print(f"Original: #{receipt_id} {vendor_name} ${gross_amount} ({payment_method})")
    
    # Define the splits
    splits = [
        {"gl": "6900", "amount": Decimal("28.05"), "method": "cash", "notes": "Vehicle Maintenance"},
        {"gl": "6500", "amount": Decimal("30.19"), "method": "cash", "notes": "Driver Meal on Duty"}
    ]
    
    # Verify total
    total = sum(s["amount"] for s in splits)
    print(f"Split total: ${total}")
    if total != gross_amount:
        print(f"ERROR: Split total ${total} != original ${gross_amount}")
        conn.close()
        exit(1)
    
    # Get max receipt ID to generate child IDs
    cur.execute("SELECT MAX(receipt_id) FROM receipts")
    max_id = cur.fetchone()[0] or 0
    
    # Create child receipts
    child_ids = []
    split_group_id = receipt_id  # Parent ID is the split group
    
    for i, split in enumerate(splits):
        new_id = max_id + i + 1
        cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, payment_method,
            gl_account_code, description,
            split_group_id, is_split_receipt, split_group_total
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING receipt_id
        """, (
            receipt_date,
            vendor_name,
            split["amount"],
            split["method"],
            split["gl"],
            split["notes"],
            split_group_id,
            True,
            gross_amount
        ))
        new_id = cur.fetchone()[0]
        child_ids.append(new_id)
        print(f"  Created child #{new_id}: GL {split['gl']} ${split['amount']} ({split['method']})")
    
    # Delete original receipt
    cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
    print(f"Deleted original receipt #{receipt_id}")
    
    conn.commit()
    print(f"\n✅ Successfully created splits!")
    print(f"   Child receipts: {child_ids}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()

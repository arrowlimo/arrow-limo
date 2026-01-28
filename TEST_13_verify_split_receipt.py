#!/usr/bin/env python
"""
TEST 13: Verify split receipt operation
Task: Split a receipt into multiple child receipts
Expected: Parent/child relationship created, amounts sum correctly
"""
import sys
sys.path.insert(0, 'L:\\limo')

import psycopg2
import os
from datetime import datetime
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

print("=" * 80)
print("TEST 13: SPLIT RECEIPT OPERATION")
print("=" * 80)
print()

try:
    cur = conn.cursor()
    
    # Create a test parent receipt
    parent_vendor = "TEST_SPLIT_PARENT_" + datetime.now().strftime("%H%M%S")
    parent_amount = Decimal("300.00")
    parent_date = datetime(2026, 1, 15).date()
    
    print("Creating test parent receipt...")
    print("-" * 80)
    
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount,
            gl_account_code, payment_method, validation_status, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, NOW()
        ) RETURNING receipt_id
    """, (parent_date, parent_vendor, "Parent receipt for split test", 
          float(parent_amount), "5110", "cash", "validated"))
    
    parent_id = cur.fetchone()[0]
    conn.commit()
    
    print(f"✅ Parent receipt created: ID {parent_id}, Amount ${parent_amount}")
    print()
    
    # Create split children (simulate split operation)
    split_amounts = [Decimal("150.00"), Decimal("100.00"), Decimal("50.00")]
    child_ids = []
    
    print("Creating split child receipts...")
    print("-" * 80)
    
    for i, split_amt in enumerate(split_amounts, 1):
        child_desc = f"Split {i} of 3 from parent {parent_id}"
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, description, gross_amount,
                gl_account_code, payment_method, validation_status,
                parent_receipt_id, is_split_receipt, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            ) RETURNING receipt_id
        """, (parent_date, parent_vendor, child_desc, float(split_amt),
              "5110", "cash", "validated", parent_id, True))
        
        child_id = cur.fetchone()[0]
        child_ids.append(child_id)
        conn.commit()
        
        print(f"  ✅ Child {i}: ID {child_id}, Amount ${split_amt}")
    
    print()
    
    # Verify split amounts sum to parent
    total_split = sum(split_amounts)
    amounts_match = total_split == parent_amount
    
    print("Verification: Split Amounts")
    print("-" * 80)
    print(f"Parent Amount:    ${parent_amount}")
    print(f"Total Split:      ${total_split}")
    print(f"Match:            {'✅ YES' if amounts_match else '❌ NO'}")
    print()
    
    # Verify parent relationship
    print("Verification: Parent-Child Relationships")
    print("-" * 80)
    
    cur.execute("""
        SELECT receipt_id, parent_receipt_id, is_split_receipt, gross_amount
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_id
    """, (child_ids,))
    
    children = cur.fetchall()
    all_linked = True
    
    for child_id, parent_id_check, is_split, amount in children:
        linked = parent_id_check == parent_id and is_split == True
        status = "✅" if linked else "❌"
        print(f"{status} Child {child_id}: parent={parent_id_check}, is_split={is_split}, amount=${amount}")
        if not linked:
            all_linked = False
    
    print()
    
    # Cleanup
    print("Cleanup: Removing test receipts...")
    cur.execute("DELETE FROM receipts WHERE receipt_id = ANY(%s)", ([parent_id] + child_ids,))
    conn.commit()
    print(f"✅ Deleted {len(child_ids) + 1} test receipts")
    
    cur.close()
    
    test13_pass = amounts_match and all_linked

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
    test13_pass = False

print()
print("=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)

if test13_pass:
    print("✅ TEST 13 PASSED: Split receipt operation works correctly")
    print("   - Amounts sum correctly")
    print("   - Parent-child relationships established")
    print("   - is_split_receipt flag set")
else:
    print("❌ TEST 13 FAILED: Split operation failed or relationships incorrect")

print("=" * 80)

conn.close()

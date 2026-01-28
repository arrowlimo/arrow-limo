#!/usr/bin/env python
"""
TEST 12: Verify update receipt operation
Task: Modify existing receipt and verify changes
Expected: Receipt UPDATE works, changed fields saved
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
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

print("=" * 80)
print("TEST 12: UPDATE RECEIPT OPERATION")
print("=" * 80)
print()

try:
    cur = conn.cursor()
    
    # Find an existing receipt to update
    cur.execute("SELECT receipt_id FROM receipts LIMIT 1")
    result = cur.fetchone()
    
    if not result:
        print("❌ No receipts found to update")
        cur.close()
        conn.close()
        exit(1)
    
    receipt_id = result[0]
    
    # Get original data
    cur.execute("""
        SELECT receipt_date, vendor_name, description, gross_amount,
               gl_account_code, payment_method
        FROM receipts WHERE receipt_id = %s
    """, (receipt_id,))
    
    orig_data = cur.fetchone()
    print(f"Original Receipt ID: {receipt_id}")
    print(f"Original Data: {orig_data}")
    print()
    
    # Update with new values
    new_description = "UPDATED_" + datetime.now().strftime("%H%M%S")
    new_amount = Decimal("199.99")
    new_payment = "check"
    
    update_query = """
        UPDATE receipts
        SET description = %s,
            gross_amount = %s,
            payment_method = %s
        WHERE receipt_id = %s
    """
    
    cur.execute(update_query, (new_description, float(new_amount), new_payment, receipt_id))
    conn.commit()
    
    print(f"✅ Receipt updated successfully")
    print(f"   New description: {new_description}")
    print(f"   New amount: ${new_amount}")
    print(f"   New payment_method: {new_payment}")
    print()
    
    # Verify the changes
    cur.execute("""
        SELECT description, gross_amount, payment_method
        FROM receipts WHERE receipt_id = %s
    """, (receipt_id,))
    
    updated_data = cur.fetchone()
    desc, amount, pay_method = updated_data
    
    print("Verification:")
    print("-" * 80)
    
    tests = [
        ("Description", new_description, desc),
        ("Amount", str(new_amount), str(amount)),
        ("Payment Method", new_payment, pay_method),
    ]
    
    passed = 0
    for field_name, expected, actual in tests:
        match = str(expected) == str(actual)
        status = "✅" if match else "❌"
        print(f"{status} {field_name}: {actual}")
        if match:
            passed += 1
    
    print()
    
    # Restore original data
    print("Restoring original data...")
    restore_query = """
        UPDATE receipts
        SET description = %s,
            gross_amount = %s,
            payment_method = %s
        WHERE receipt_id = %s
    """
    
    cur.execute(restore_query, (orig_data[2], orig_data[4], orig_data[5], receipt_id))
    conn.commit()
    print("✅ Original data restored")
    
    cur.close()
    
    test12_pass = passed == len(tests)

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
    test12_pass = False

print()
print("=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)

if test12_pass:
    print("✅ TEST 12 PASSED: Update receipt operation works correctly")
else:
    print("❌ TEST 12 FAILED: Update operation failed or data mismatch")

print("=" * 80)

conn.close()

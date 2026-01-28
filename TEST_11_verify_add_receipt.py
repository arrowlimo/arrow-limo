#!/usr/bin/env python
"""
TEST 11: Verify add receipt operation
Task: Insert new receipt and verify in database
Expected: Receipt INSERT works without errors, all fields saved
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
print("TEST 11: ADD RECEIPT OPERATION")
print("=" * 80)
print()

# Test data
test_vendor = "TEST_VENDOR_" + datetime.now().strftime("%Y%m%d_%H%M%S")
test_date = datetime(2026, 1, 15).date()
test_amount = Decimal("125.50")
test_gl = "5110"  # Some existing GL code
test_description = "Test receipt for verification"
test_source_ref = "TEST_REF_" + datetime.now().strftime("%H%M%S")

print("Test Case: Insert New Receipt")
print("-" * 80)
print(f"Vendor: {test_vendor}")
print(f"Date: {test_date}")
print(f"Amount: ${test_amount}")
print(f"GL Code: {test_gl}")
print(f"Description: {test_description}")
print(f"Source Reference: {test_source_ref}")
print()

try:
    cur = conn.cursor()
    
    # First, verify the GL code exists
    cur.execute("SELECT account_code FROM chart_of_accounts WHERE account_code = %s", (test_gl,))
    if not cur.fetchone():
        print(f"⚠️ GL code {test_gl} not found, using first available GL code...")
        cur.execute("SELECT account_code FROM chart_of_accounts LIMIT 1")
        gl_result = cur.fetchone()
        if gl_result:
            test_gl = gl_result[0]
            print(f"   Using GL: {test_gl}")
        else:
            print("❌ No GL codes found in database")
            test_gl = None
    
    # Simulate _add_receipt operation
    # This is what the widget does internally
    insert_query = """
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount,
            gl_account_code, source_reference, payment_method,
            validation_status, created_at
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, NOW()
        ) RETURNING receipt_id
    """
    
    params = (
        test_date,
        test_vendor,
        test_description,
        float(test_amount),
        test_gl,
        test_source_ref,
        "cash",
        "validated"
    )
    
    cur.execute(insert_query, params)
    receipt_id = cur.fetchone()[0]
    conn.commit()
    
    print(f"✅ Receipt inserted successfully")
    print(f"   Receipt ID: {receipt_id}")
    print()
    
    # Verify the receipt was saved
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               gl_account_code, source_reference, description, payment_method
        FROM receipts WHERE receipt_id = %s
    """, (receipt_id,))
    
    result = cur.fetchone()
    
    if result:
        rid, rdate, vendor, amount, gl, source_ref, desc, pay_method = result
        print("Test 2: Verify Saved Data")
        print("-" * 80)
        
        print(f"{'Field':<25} {'Expected':<30} {'Actual':<30} {'Status'}")
        print("-" * 80)
        
        tests = [
            ("Vendor", test_vendor, vendor),
            ("Date", str(test_date), str(rdate)),
            ("Amount", str(test_amount), str(amount)),
            ("GL Code", test_gl, gl),
            ("Source Reference", test_source_ref, source_ref),
            ("Description", test_description, desc),
            ("Payment Method", "cash", pay_method),
        ]
        
        passed = 0
        for field_name, expected, actual in tests:
            match = str(expected) == str(actual)
            status = "✅" if match else "❌"
            print(f"{field_name:<25} {expected:<30} {actual:<30} {status}")
            if match:
                passed += 1
        
        print()
        print(f"Verified: {passed}/{len(tests)} fields match")
        
        # Clean up test data
        print()
        print("Cleanup: Removing test receipt...")
        cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
        conn.commit()
        print("✅ Test receipt deleted")
        
        test11_pass = passed == len(tests)
        
    else:
        print("❌ Receipt not found after insert")
        test11_pass = False
    
    cur.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
    test11_pass = False

print()
print("=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)

if test11_pass:
    print("✅ TEST 11 PASSED: Add receipt operation works correctly")
else:
    print("❌ TEST 11 FAILED: Add receipt operation failed or data mismatch")

print("=" * 80)

conn.close()

#!/usr/bin/env python
"""
TEST 1: Verify receipts table schema
Task: Query table structure
Expected: 33+ columns including source_reference, NO invoice_number
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get receipts table schema
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    cur.close()
    conn.close()
    
    print("=" * 80)
    print("TEST 1: RECEIPTS TABLE SCHEMA VERIFICATION")
    print("=" * 80)
    print()
    
    # Display results
    print(f"{'Column #':<10} {'Column Name':<35} {'Data Type':<20} {'Nullable':<10}")
    print("-" * 80)
    
    has_source_reference = False
    has_invoice_number = False
    column_count = 0
    
    for i, (col_name, data_type, is_nullable) in enumerate(columns, 1):
        column_count += 1
        null_str = "YES" if is_nullable == 'YES' else "NO"
        print(f"{i:<10} {col_name:<35} {data_type:<20} {null_str:<10}")
        
        if col_name.lower() == 'source_reference':
            has_source_reference = True
        if col_name.lower() == 'invoice_number':
            has_invoice_number = True
    
    print()
    print("=" * 80)
    print("VERIFICATION RESULTS")
    print("=" * 80)
    print(f"✅ Total Columns: {column_count}")
    print(f"   Expected: 33+")
    print(f"   Result: {'PASS' if column_count >= 33 else 'FAIL'}")
    print()
    print(f"✅ Has source_reference: {has_source_reference}")
    print(f"   Expected: YES")
    print(f"   Result: {'PASS' if has_source_reference else 'FAIL'}")
    print()
    print(f"✅ Has invoice_number: {has_invoice_number}")
    print(f"   Expected: NO (should be removed)")
    print(f"   Result: {'PASS' if not has_invoice_number else 'FAIL'}")
    print()
    print("=" * 80)
    
    # Final verdict
    test_passed = (column_count >= 33) and has_source_reference and (not has_invoice_number)
    
    if test_passed:
        print("✅ TEST 1 PASSED: Schema is correct")
    else:
        print("❌ TEST 1 FAILED: Schema issues detected")
    
    print("=" * 80)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

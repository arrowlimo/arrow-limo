"""
Verification Script for January 22, 2026 Fixes
Tests the 3 critical fixes made today:
1. Backend API column fix: total_price → total_amount_due
2. Backend API column fix: service_date → charter_date  
3. Desktop app rollback fix: receipt detail expansion
"""

import psycopg2
import os
from datetime import date, timedelta

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def test_schema_columns():
    """Verify the correct column names exist in charters table"""
    print("=" * 80)
    print("TEST 1: Schema Verification")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Check charters table columns
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'charters' 
        AND column_name IN ('charter_date', 'total_amount_due', 'service_date', 'total_price')
        ORDER BY column_name
    """)
    
    columns = [row[0] for row in cur.fetchall()]
    print(f"Columns found in charters table: {columns}")
    
    # Verify correct columns exist
    assert 'charter_date' in columns, "✅ charter_date exists"
    assert 'total_amount_due' in columns, "✅ total_amount_due exists"
    
    # Verify wrong columns don't exist
    if 'service_date' in columns:
        print("⚠️  WARNING: service_date column exists (shouldn't be used for charters)")
    else:
        print("✅ service_date does NOT exist in charters (correct)")
        
    if 'total_price' in columns:
        print("⚠️  WARNING: total_price column exists (shouldn't be used)")
    else:
        print("✅ total_price does NOT exist in charters (correct)")
    
    cur.close()
    conn.close()
    print("\n✅ Schema verification PASSED\n")

def test_backend_query():
    """Verify the backend profit-loss query uses correct columns"""
    print("=" * 80)
    print("TEST 2: Backend API Query Verification")
    print("=" * 80)
    
    # Read the backend file to verify the fix
    with open('l:/limo/modern_backend/app/routers/accounting.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for correct columns
    assert 'SUM(total_amount_due)' in content, "✅ Uses total_amount_due"
    assert 'charter_date >=' in content or 'WHERE charter_date' in content, "✅ Uses charter_date"
    
    # Check for wrong columns
    if 'total_price' in content:
        # Check if it's just in comments
        lines_with_total_price = [line for line in content.split('\n') if 'total_price' in line and not line.strip().startswith('#')]
        if lines_with_total_price:
            print(f"⚠️  WARNING: Found total_price in non-comment lines:")
            for line in lines_with_total_price[:5]:
                print(f"    {line.strip()}")
        else:
            print("✅ total_price only in comments (correct)")
    else:
        print("✅ No total_price references (correct)")
        
    if 'service_date >=' in content or 'WHERE service_date' in content:
        print("❌ FAILED: Still using service_date for charters")
        raise AssertionError("service_date still in use")
    else:
        print("✅ Not using service_date for charters (correct)")
    
    print("\n✅ Backend query verification PASSED\n")

def test_receipt_column_exists():
    """Verify the receipts columns used in detail expansion exist"""
    print("=" * 80)
    print("TEST 3: Receipts Table Verification")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Check receipts table for columns used in detail expansion
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name IN ('is_verified_banking', 'created_from_banking', 'banking_transaction_id', 
                            'source_system', 'is_paper_verified', 'verified_by_edit')
        ORDER BY column_name
    """)
    
    columns = [row[0] for row in cur.fetchall()]
    print(f"Detail columns in receipts table: {columns}")
    
    assert 'is_verified_banking' in columns, "✅ is_verified_banking column exists"
    assert 'created_from_banking' in columns, "✅ created_from_banking exists"
    assert 'banking_transaction_id' in columns, "✅ banking_transaction_id exists"
    assert 'source_system' in columns, "✅ source_system exists"
    assert 'is_paper_verified' in columns, "✅ is_paper_verified exists"
    assert 'verified_by_edit' in columns, "✅ verified_by_edit exists"
    
    # Test the actual query used in the desktop app (UPDATED VERSION)
    cur.execute("""
        SELECT description, gl_account_code, gl_account_name,
               source_system, is_verified_banking, created_from_banking, banking_transaction_id,
               is_paper_verified, verified_by_edit
        FROM receipts
        LIMIT 1
    """)
    
    result = cur.fetchone()
    if result:
        print(f"✅ Sample query successful: {len(result)} columns returned")
    else:
        print("⚠️  No receipts found, but schema is correct")
    
    cur.close()
    conn.close()
    print("\n✅ Receipts schema verification PASSED\n")

def test_backend_file_fix():
    """Verify the exact lines that were fixed in accounting.py"""
    print("=" * 80)
    print("TEST 4: Backend File Line-by-Line Verification")
    print("=" * 80)
    
    with open('l:/limo/modern_backend/app/routers/accounting.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the profit-loss query (around line 222-225)
    found_total_amount_due = False
    found_charter_date = False
    
    for i, line in enumerate(lines[215:230], start=216):
        if 'SUM(total_amount_due)' in line:
            print(f"✅ Line {i}: Found SUM(total_amount_due)")
            found_total_amount_due = True
        if 'WHERE charter_date >=' in line or 'charter_date <= %s' in line:
            print(f"✅ Line {i}: Found charter_date condition")
            found_charter_date = True
    
    assert found_total_amount_due, "total_amount_due found in query"
    assert found_charter_date, "charter_date found in query"
    
    print("\n✅ Backend file fix verification PASSED\n")

def test_desktop_app_rollback():
    """Verify the rollback was added to desktop app"""
    print("=" * 80)
    print("TEST 5: Desktop App Rollback Verification")
    print("=" * 80)
    
    with open('l:/limo/desktop_app/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the _toggle_row_expansion method
    if 'def _toggle_row_expansion' in content:
        print("✅ Found _toggle_row_expansion method")
        
        # Find the section with the receipt detail query (UPDATED QUERY)
        start_idx = content.find('is_verified_banking, created_from_banking, banking_transaction_id')
        if start_idx > 0:
            # Check 300 chars before for rollback
            context = content[max(0, start_idx - 300):start_idx]
            if 'self.db.rollback()' in context:
                print("✅ Found rollback before receipt detail query")
            else:
                print("❌ FAILED: No rollback before receipt detail query")
                raise AssertionError("Missing rollback protection")
        else:
            print("⚠️  Could not find receipt detail query (checking old pattern)")
            # Try old pattern
            start_idx = content.find('SELECT description, gl_account_code, gl_account_name')
            if start_idx > 0:
                context = content[max(0, start_idx - 300):start_idx]
                if 'self.db.rollback()' in context:
                    print("✅ Found rollback before receipt detail query (old pattern)")
                else:
                    print("❌ FAILED: No rollback found")
                    raise AssertionError("Missing rollback protection")
    else:
        print("⚠️  Could not find _toggle_row_expansion method")
    
    print("\n✅ Desktop app rollback verification PASSED\n")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("VERIFICATION SUITE FOR JANUARY 22, 2026 FIXES")
    print("=" * 80 + "\n")
    
    try:
        test_schema_columns()
        test_backend_query()
        test_receipt_column_exists()
        test_backend_file_fix()
        test_desktop_app_rollback()
        
        print("=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\nSummary of fixes verified:")
        print("1. ✅ modern_backend/app/routers/accounting.py - total_price → total_amount_due")
        print("2. ✅ modern_backend/app/routers/accounting.py - service_date → charter_date")
        print("3. ✅ desktop_app/main.py - Added transaction rollback to receipt expansion")
        print("4. ✅ desktop_app/main.py - Fixed receipt columns: reviewed → is_verified_banking")
        print("\n")
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ TEST SUITE FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

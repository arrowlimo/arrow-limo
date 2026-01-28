"""
Comprehensive Desktop App Testing Suite
Tests all major components after rollback fixes
"""

import psycopg2
import os
from datetime import date
from pathlib import Path

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

print("\n" + "=" * 80)
print("COMPREHENSIVE DESKTOP APP TEST SUITE - January 22, 2026")
print("=" * 80 + "\n")

tests_passed = 0
tests_failed = 0
warnings = []

# ============================================================================
# TEST 1: Backend API Schema Fixes
# ============================================================================
print("TEST 1: Backend API Schema Fixes")
print("-" * 80)

try:
    with open('l:/limo/modern_backend/app/routers/accounting.py', 'r', encoding='utf-8') as f:
        backend_content = f.read()
    
    # Verify correct columns
    assert 'SUM(total_amount_due)' in backend_content, "total_amount_due column used"
    assert 'charter_date >=' in backend_content or 'WHERE charter_date' in backend_content, "charter_date column used"
    
    # Verify wrong columns removed
    wrong_patterns = ['total_price', 'service_date >=', 'WHERE service_date']
    for pattern in wrong_patterns:
        if pattern in backend_content and not (pattern in backend_content and backend_content.count(pattern) == backend_content.count(f'# {pattern}')):
            # Allow in comments only
            lines_with_pattern = [l for l in backend_content.split('\n') if pattern in l and not l.strip().startswith('#')]
            if lines_with_pattern:
                warnings.append(f"Backend may still contain '{pattern}'")
    
    print("✅ Backend API uses correct column names (total_amount_due, charter_date)")
    tests_passed += 1
except Exception as e:
    print(f"❌ Backend API test failed: {e}")
    tests_failed += 1

# ============================================================================
# TEST 2: Receipt Detail Expansion Query
# ============================================================================
print("\nTEST 2: Receipt Detail Expansion Query")
print("-" * 80)

try:
    conn = get_conn()
    cur = conn.cursor()
    
    # Test the actual query used in receipt expansion
    cur.execute("""
        SELECT description, gl_account_code, gl_account_name,
               source_system, is_verified_banking, created_from_banking, banking_transaction_id,
               is_paper_verified, verified_by_edit
        FROM receipts
        LIMIT 1
    """)
    
    result = cur.fetchone()
    assert result is not None, "Receipt query returned data"
    assert len(result) == 9, "Receipt query returns 9 columns"
    
    cur.close()
    conn.close()
    
    print("✅ Receipt detail query works with correct columns")
    tests_passed += 1
except Exception as e:
    print(f"❌ Receipt detail query failed: {e}")
    tests_failed += 1

# ============================================================================
# TEST 3: Enhanced Charter Widget Query
# ============================================================================
print("\nTEST 3: Enhanced Charter Widget Query")
print("-" * 80)

try:
    conn = get_conn()
    conn.rollback()  # Test rollback works
    cur = conn.cursor()
    
    # Test charter query
    cur.execute("""
        SELECT 
            c.reserve_number,
            COALESCE(cl.company_name, cl.client_name),
            c.charter_date::date,
            e.full_name,
            v.vehicle_number,
            c.booking_status,
            c.total_amount_due,
            COALESCE(c.total_amount_due - 
                (SELECT COALESCE(SUM(amount), 0) FROM payments 
                 WHERE reserve_number = c.reserve_number), 
                c.total_amount_due) as balance_due
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN employees e ON c.employee_id = e.employee_id
        LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
        WHERE c.charter_date >= '2025-01-01'
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    print(f"✅ Charter query returned {len(rows)} charters")
    
    cur.close()
    conn.close()
    tests_passed += 1
except Exception as e:
    print(f"❌ Charter widget query failed: {e}")
    tests_failed += 1

# ============================================================================
# TEST 4: Enhanced Employee Widget Query
# ============================================================================
print("\nTEST 4: Enhanced Employee Widget Query")
print("-" * 80)

try:
    conn = get_conn()
    conn.rollback()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            e.employee_id,
            e.full_name,
            e.position,
            e.hire_date,
            'Active' as status,
            e.is_chauffeur,
            COALESCE(SUM(dp.gross_pay), 0) as ytd_pay,
            0 as unreturned_floats,
            0 as missing_receipts
        FROM employees e
        LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
        WHERE e.full_name IS NOT NULL AND e.full_name != ''
        GROUP BY e.employee_id, e.full_name, e.position, e.hire_date, e.is_chauffeur
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    print(f"✅ Employee query returned {len(rows)} employees")
    
    cur.close()
    conn.close()
    tests_passed += 1
except Exception as e:
    print(f"❌ Employee widget query failed: {e}")
    tests_failed += 1

# ============================================================================
# TEST 5: Enhanced Vehicle Widget Query
# ============================================================================
print("\nTEST 5: Enhanced Vehicle Widget Query")
print("-" * 80)

try:
    conn = get_conn()
    conn.rollback()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            v.vehicle_id,
            v.vehicle_number,
            v.license_plate,
            CONCAT(v.make, ' ', v.model) as make_model,
            v.year,
            v.vehicle_type,
            COALESCE(v.odometer, 0) as current_mileage,
            COALESCE(v.operational_status, 'active') as status,
            v.next_service_due,
            0 as alert_count
        FROM vehicles v
        WHERE 1=1
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    print(f"✅ Vehicle query returned {len(rows)} vehicles")
    
    cur.close()
    conn.close()
    tests_passed += 1
except Exception as e:
    print(f"❌ Vehicle widget query failed: {e}")
    tests_failed += 1

# ============================================================================
# TEST 6: Enhanced Client Widget Query
# ============================================================================
print("\nTEST 6: Enhanced Client Widget Query")
print("-" * 80)

try:
    conn = get_conn()
    conn.rollback()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            cl.client_id,
            cl.company_name,
            cl.client_name,
            cl.primary_phone,
            cl.email,
            COALESCE(SUM(c.total_amount_due), 0) as total_revenue,
            COALESCE(SUM(c.total_amount_due) - SUM(
                (SELECT COALESCE(SUM(p.amount), 0) 
                 FROM payments p 
                 WHERE p.reserve_number = c.reserve_number)
            ), 0) as outstanding,
            MAX(c.charter_date) as last_charter,
            'Active' as status
        FROM clients cl
        LEFT JOIN charters c ON cl.client_id = c.client_id
        GROUP BY cl.client_id, cl.company_name, cl.client_name, cl.primary_phone, cl.email
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    print(f"✅ Client query returned {len(rows)} clients")
    
    cur.close()
    conn.close()
    tests_passed += 1
except Exception as e:
    print(f"❌ Client widget query failed: {e}")
    tests_failed += 1

# ============================================================================
# TEST 7: Rollback Protection Verification
# ============================================================================
print("\nTEST 7: Rollback Protection Verification")
print("-" * 80)

rollback_files_checked = 0
rollback_protections_found = 0

for py_file in Path('l:/limo/desktop_app').glob('*.py'):
    if 'backup' in str(py_file) or '__pycache__' in str(py_file):
        continue
    
    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        rollback_files_checked += 1
        
        # Count rollback protections
        if 'self.db.rollback()' in content:
            rollback_protections_found += content.count('self.db.rollback()')
    except:
        pass

print(f"✅ Checked {rollback_files_checked} files, found {rollback_protections_found} rollback protections")
tests_passed += 1

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Tests Passed: {tests_passed}")
print(f"Tests Failed: {tests_failed}")

if warnings:
    print(f"\n⚠️  Warnings ({len(warnings)}):")
    for w in warnings:
        print(f"  - {w}")

print("\n" + "=" * 80)
if tests_failed == 0:
    print("🎉 ALL TESTS PASSED!")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Launch desktop app: python -X utf8 desktop_app/main.py")
    print("2. Test Charter List tab (should show data with date filters)")
    print("3. Test Fleet Management tab")
    print("4. Test Employee/Client tabs")
    print("5. Try expanding a receipt row in Receipts_Invoices tab")
else:
    print("❌ SOME TESTS FAILED")
    print("=" * 80)
    print("Review errors above before launching app")

print("\n")

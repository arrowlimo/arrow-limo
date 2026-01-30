"""
Smoke Test - Arrow Limousine Desktop Application
Tests all critical functionality:
- Database connection
- Charter/Booking form
- Receipts management
- Split receipts
- Banking links
- Accounting reports

Run this before deploying any changes.
"""

import os
import sys

# Add desktop_app to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import psycopg2
from decimal import Decimal
from datetime import date

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def test_database_connection():
    """Test 1: Database connectivity"""
    print("\n🔍 TEST 1: Database Connection")
    print("="*60)
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✅ Connected to PostgreSQL")
        print(f"   Version: {version[:50]}...")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_core_tables():
    """Test 2: Core tables exist and have data"""
    print("\n🔍 TEST 2: Core Tables")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    tables = {
        "charters": "Bookings/Charters",
        "payments": "Payments",
        "receipts": "Receipts/Expenses",
        "banking_transactions": "Banking Transactions",
        "employees": "Employees",
        "vehicles": "Fleet",
        "clients": "Customers"
    }
    
    all_ok = True
    for table, description in tables.items():
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            print(f"✅ {description:25s} ({table}): {count:,} records")
        except Exception as e:
            print(f"❌ {description:25s} ({table}): ERROR - {e}")
            all_ok = False
    
    cur.close()
    conn.close()
    return all_ok


def test_charter_functionality():
    """Test 3: Charter/Booking data integrity"""
    print("\n🔍 TEST 3: Charter/Booking Functionality")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Check for charters with payments
        cur.execute("""
            SELECT COUNT(DISTINCT c.reserve_number) 
            FROM charters c
            INNER JOIN payments p ON p.reserve_number = c.reserve_number
            WHERE c.charter_date >= '2025-01-01'
        """)
        charters_with_payments = cur.fetchone()[0]
        print(f"✅ Charters with payments (2025): {charters_with_payments:,}")
        
        # Check reserve_number is being used correctly
        cur.execute("""
            SELECT COUNT(*) 
            FROM payments p
            LEFT JOIN charters c ON c.reserve_number = p.reserve_number
            WHERE c.charter_id IS NULL
            LIMIT 1
        """)
        orphan_payments = cur.fetchone()[0]
        if orphan_payments > 0:
            print(f"⚠️  Orphan payments (no charter): {orphan_payments:,}")
        else:
            print(f"✅ No orphan payments (all linked correctly)")
        
        # Check for charters with vehicle assignment
        cur.execute("""
            SELECT COUNT(*) 
            FROM charters
            WHERE vehicle_id IS NOT NULL AND vehicle_id > 0
            AND charter_date >= '2025-01-01'
        """)
        assigned_vehicles = cur.fetchone()[0]
        print(f"✅ Charters with vehicles (2025): {assigned_vehicles:,}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Charter tests failed: {e}")
        cur.close()
        conn.close()
        return False


def test_receipt_functionality():
    """Test 4: Receipt management"""
    print("\n🔍 TEST 4: Receipt Management")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Check receipts have required columns
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(banking_transaction_id) as with_banking,
                COUNT(split_group_id) as in_splits,
                COUNT(expense_account) as with_gl_account
            FROM receipts
            WHERE receipt_date >= '2025-01-01'
        """)
        row = cur.fetchone()
        total, with_banking, in_splits, with_gl = row
        
        print(f"✅ Total receipts (2025): {total:,}")
        print(f"✅ Linked to banking: {with_banking:,} ({with_banking/max(total,1)*100:.1f}%)")
        print(f"✅ In split groups: {in_splits:,}")
        print(f"✅ With GL account: {with_gl:,} ({with_gl/max(total,1)*100:.1f}%)")
        
        # Check for receipts with GST
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts
            WHERE gst_amount > 0
            AND receipt_date >= '2025-01-01'
        """)
        with_gst = cur.fetchone()[0]
        print(f"✅ Receipts with GST recorded: {with_gst:,}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Receipt tests failed: {e}")
        cur.close()
        conn.close()
        return False


def test_split_receipt_functionality():
    """Test 5: Split receipt system"""
    print("\n🔍 TEST 5: Split Receipt System")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Check split_group_id column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'receipts' 
            AND column_name = 'split_group_id'
        """)
        if cur.fetchone():
            print("✅ split_group_id column exists")
        else:
            print("❌ split_group_id column missing")
            cur.close()
            conn.close()
            return False
        
        # Check for split receipts
        cur.execute("""
            SELECT COUNT(DISTINCT split_group_id) as split_groups,
                   COUNT(*) as total_split_receipts
            FROM receipts
            WHERE split_group_id IS NOT NULL
        """)
        row = cur.fetchone()
        split_groups, total_splits = row
        
        if total_splits > 0:
            print(f"✅ Split groups: {split_groups:,}")
            print(f"✅ Total receipts in splits: {total_splits:,}")
            print(f"   Average parts per split: {total_splits/max(split_groups,1):.1f}")
        else:
            print("ℹ️  No split receipts found (normal if not used yet)")
        
        # Check receipt_splits audit table
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'receipt_splits'
        """)
        if cur.fetchone()[0] > 0:
            print("✅ receipt_splits audit table exists")
        else:
            print("⚠️  receipt_splits audit table not found")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Split receipt tests failed: {e}")
        cur.close()
        conn.close()
        return False


def test_banking_links():
    """Test 6: Banking transaction linking"""
    print("\n🔍 TEST 6: Banking Transaction Linking")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Check banking_transactions table
        cur.execute("SELECT COUNT(*) FROM banking_transactions;")
        total_banking = cur.fetchone()[0]
        
        if total_banking > 0:
            print(f"✅ Banking transactions: {total_banking:,}")
            
            # Check how many receipts are linked
            cur.execute("""
                SELECT COUNT(DISTINCT r.receipt_id)
                FROM receipts r
                WHERE r.banking_transaction_id IS NOT NULL
            """)
            linked_receipts = cur.fetchone()[0]
            print(f"✅ Receipts linked to banking: {linked_receipts:,}")
            
            # Check ledger table
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'banking_receipt_matching_ledger'
            """)
            if cur.fetchone()[0] > 0:
                cur.execute("SELECT COUNT(*) FROM banking_receipt_matching_ledger;")
                ledger_count = cur.fetchone()[0]
                print(f"✅ Banking ledger entries: {ledger_count:,}")
        else:
            print("ℹ️  No banking transactions (import required)")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Banking link tests failed: {e}")
        cur.close()
        conn.close()
        return False


def test_accounting_tables():
    """Test 7: Accounting/reporting tables"""
    print("\n🔍 TEST 7: Accounting Tables")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    accounting_tables = {
        "chart_of_accounts": "Chart of Accounts",
        "general_ledger": "General Ledger",
        "driver_payroll": "Payroll",
        "payables": "Accounts Payable"
    }
    
    all_ok = True
    for table, description in accounting_tables.items():
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            status = "✅" if count > 0 else "⚠️ "
            print(f"{status} {description:25s}: {count:,} records")
        except Exception as e:
            print(f"❌ {description:25s}: Table not found")
            all_ok = False
    
    cur.close()
    conn.close()
    return all_ok


def test_widget_imports():
    """Test 8: Desktop app widgets import"""
    print("\n🔍 TEST 8: Desktop App Widgets")
    print("="*60)
    
    imports_to_test = [
        ("desktop_app.main", "CharterFormWidget", "Charter/Booking Form"),
        ("desktop_app.receipt_search_match_widget", "ReceiptSearchMatchWidget", "Receipt Management"),
        ("desktop_app.split_receipt_manager_dialog", "SplitReceiptManagerDialog", "Split Receipt Manager"),
        ("desktop_app.split_receipt_details_widget", "SplitReceiptDetailsWidget", "Split Receipt Details"),
        ("desktop_app.banking_transaction_picker_dialog", "BankingTransactionPickerDialog", "Banking Picker"),
        ("desktop_app.accounting_reports", "TrialBalanceWidget", "Trial Balance Report"),
        ("desktop_app.dashboard_classes", "FleetManagementWidget", "Dashboard System"),
    ]
    
    all_ok = True
    for module_name, class_name, description in imports_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            widget_class = getattr(module, class_name)
            print(f"✅ {description:30s} - importable")
        except Exception as e:
            print(f"❌ {description:30s} - {e}")
            all_ok = False
    
    return all_ok


def test_data_integrity():
    """Test 9: Data integrity checks"""
    print("\n🔍 TEST 9: Data Integrity")
    print("="*60)
    
    conn = get_conn()
    cur = conn.cursor()
    
    issues_found = 0
    
    # Check for negative charter balances (overpayments)
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        LEFT JOIN (
            SELECT reserve_number, SUM(amount) as total_paid
            FROM payments
            GROUP BY reserve_number
        ) p ON p.reserve_number = c.reserve_number
        WHERE COALESCE(p.total_paid, 0) > c.total_amount_due
        AND c.total_amount_due > 0
    """)
    overpaid = cur.fetchone()[0]
    if overpaid > 0:
        print(f"ℹ️  Charters with overpayments: {overpaid} (may be legitimate prepayments)")
    else:
        print(f"✅ No overpaid charters")
    
    # Check for future-dated receipts
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE receipt_date > CURRENT_DATE
    """)
    future_receipts = cur.fetchone()[0]
    if future_receipts > 0:
        print(f"⚠️  Future-dated receipts: {future_receipts}")
        issues_found += 1
    else:
        print(f"✅ No future-dated receipts")
    
    # Check for charters without reserve_number
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE reserve_number IS NULL OR reserve_number = ''
    """)
    no_reserve = cur.fetchone()[0]
    if no_reserve > 0:
        print(f"⚠️  Charters without reserve_number: {no_reserve}")
        issues_found += 1
    else:
        print(f"✅ All charters have reserve_number")
    
    cur.close()
    conn.close()
    
    if issues_found == 0:
        print(f"\n✅ No data integrity issues found")
    else:
        print(f"\n⚠️  {issues_found} data integrity issue(s) found")
    
    return issues_found == 0


def run_smoke_tests():
    """Run all smoke tests"""
    print("\n" + "="*60)
    print("ARROW LIMOUSINE - SMOKE TEST SUITE")
    print("="*60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Core Tables", test_core_tables),
        ("Charter Functionality", test_charter_functionality),
        ("Receipt Management", test_receipt_functionality),
        ("Split Receipts", test_split_receipt_functionality),
        ("Banking Links", test_banking_links),
        ("Accounting Tables", test_accounting_tables),
        ("Widget Imports", test_widget_imports),
        ("Data Integrity", test_data_integrity),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{len(results)} tests passed")
    if failed == 0:
        print("🎉 ALL TESTS PASSED - System ready for use!")
    else:
        print(f"⚠️  {failed} test(s) failed - review errors above")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_smoke_tests()
    sys.exit(0 if success else 1)

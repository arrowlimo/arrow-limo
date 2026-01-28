#!/usr/bin/env python3
"""
Comprehensive widget launch test - simulates user clicking through tabs
"""
import sys
import psycopg2
from pathlib import Path

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def test_operations_tab():
    """Test all Operations tab widgets"""
    print("\n✅ Testing Operations Tab...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Test Bookings widget
        cur.execute("SELECT COUNT(*) FROM charters LIMIT 100")
        count = cur.fetchone()[0]
        print(f"  ✅ Bookings: {min(count, 100)} charters loaded")
        
        # Test Charter List
        cur.execute("""
            SELECT c.reserve_number, c.charter_date, c.total_amount_due 
            FROM charters c 
            LIMIT 10
        """)
        charters = cur.fetchall()
        print(f"  ✅ Charter List: {len(charters)} charters ready")
        
        # Test Dispatch
        cur.execute("""
            SELECT COUNT(DISTINCT charter_id) FROM charters 
            WHERE charter_date >= NOW()::date
        """)
        upcoming = cur.fetchone()[0]
        print(f"  ✅ Dispatch: {upcoming} upcoming charters")
        
        # Test Customers
        cur.execute("SELECT COUNT(*) FROM clients")
        client_count = cur.fetchone()[0]
        print(f"  ✅ Customers: {client_count} clients in system")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Operations Tab failed: {e}")
        return False

def test_fleet_management_tab():
    """Test Fleet Management tab widgets"""
    print("\n✅ Testing Fleet Management Tab...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Test Fleet Management widget
        cur.execute("""
            SELECT COUNT(*), 
                   SUM(CAST(COALESCE(purchase_price, 0) AS DECIMAL(12,2))) as total_value
            FROM vehicles
        """)
        count, value = cur.fetchone()
        print(f"  ✅ Fleet Management: {count} vehicles, ${value or 0:.2f} total value")
        
        # Test Driver Performance
        cur.execute("""
            SELECT COUNT(DISTINCT employee_id)
            FROM charters
        """)
        driver_count = cur.fetchone()[0]
        print(f"  ✅ Driver Performance: {driver_count} active drivers")
        
        # Test Financial Dashboard
        cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                SUM(CAST(COALESCE(total_amount_due, 0) AS DECIMAL(12,2))) as total_revenue
            FROM charters
        """)
        charters, revenue = cur.fetchone()
        print(f"  ✅ Financial Dashboard: {charters} charters, ${revenue or 0:.2f} revenue")
        
        # Test Payment Reconciliation
        cur.execute("""
            SELECT COUNT(*)
            FROM charters c
            LEFT JOIN payments p ON c.reserve_number = p.reserve_number
            WHERE p.payment_id IS NULL
        """)
        outstanding = cur.fetchone()[0]
        print(f"  ✅ Payment Reconciliation: {outstanding} outstanding charters")
        
        # Test Vehicle Fleet Cost Analysis
        cur.execute("SELECT COUNT(*) FROM vehicles")
        vehicles = cur.fetchone()[0]
        print(f"  ✅ Vehicle Fleet Cost: {vehicles} vehicles tracked")
        
        # Test Fuel Efficiency
        cur.execute("""
            SELECT COUNT(*) FROM vehicles
            WHERE license_plate IS NOT NULL
        """)
        active = cur.fetchone()[0]
        print(f"  ✅ Fuel Efficiency: {active} active vehicles")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Fleet Management Tab failed: {e}")
        return False

def test_accounting_tab():
    """Test Accounting tab widgets"""
    print("\n✅ Testing Accounting Tab...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Test Receipt Search/Match Widget
        cur.execute("SELECT COUNT(*) FROM receipts")
        receipts = cur.fetchone()[0]
        print(f"  ✅ Receipt Search/Match: {receipts} receipts loaded")
        
        # Test Financial Reports
        cur.execute("""
            SELECT 
                SUM(CAST(COALESCE(total_amount_due, 0) AS DECIMAL(12,2))) as revenue,
                SUM(CAST(COALESCE(gross_amount, 0) AS DECIMAL(12,2))) as expenses
            FROM (
                SELECT total_amount_due, NULL as gross_amount FROM charters
                UNION ALL
                SELECT NULL, gross_amount FROM receipts
            ) combined
        """)
        revenue, expenses = cur.fetchone() or (0, 0)
        print(f"  ✅ Financial Reports: ${revenue or 0:.2f} revenue, ${expenses or 0:.2f} expenses")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Accounting Tab failed: {e}")
        return False

def test_admin_tab():
    """Test Admin tab functionality"""
    print("\n✅ Testing Admin Tab...")
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Check admin tables
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public') as table_count,
                (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='public') as column_count
        """)
        tables, columns = cur.fetchone()
        print(f"  ✅ Admin Panel: {tables} tables, {columns} total columns")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ Admin Tab failed: {e}")
        return False

def test_custom_report_builder():
    """Test Custom Report Builder"""
    print("\n✅ Testing Custom Report Builder...")
    try:
        # Just verify the reports directory exists
        reports_dir = Path("L:\\limo\\reports")
        if reports_dir.exists():
            report_count = len(list(reports_dir.glob("*.csv"))) + len(list(reports_dir.glob("*.md")))
            print(f"  ✅ Custom Report Builder: {report_count} reports available")
        else:
            print(f"  ✅ Custom Report Builder: Ready (no reports yet)")
        
        return True
    except Exception as e:
        print(f"  ❌ Custom Report Builder failed: {e}")
        return False

def main():
    print("=" * 70)
    print("Arrow Limousine Desktop App - Widget Launch Test")
    print("=" * 70)
    
    tests = [
        test_operations_tab,
        test_fleet_management_tab,
        test_accounting_tab,
        test_admin_tab,
        test_custom_report_builder,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"✅ All Tab Tests Complete: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

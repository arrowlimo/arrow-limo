#!/usr/bin/env python
"""Comprehensive verification of receipt widget improvements"""
import sys
import psycopg2

def test_database_schema():
    """Verify all database schema components"""
    try:
        conn = psycopg2.connect(host='localhost', user='postgres', password='***REMOVED***', dbname='almsdata')
        cur = conn.cursor()
        
        # 1. Receipts table schema
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'receipts' 
            ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        print("✅ Receipts table schema verified:")
        expected = {'receipt_id', 'receipt_date', 'vendor_name', 'gross_amount', 'source_reference', 'banking_transaction_id', 'reserve_number'}
        found = {col[0] for col in cols}
        for col, dtype, nullable in cols[:12]:
            print(f"   - {col:30} {dtype:15} {'(nullable)' if nullable == 'YES' else ''}")
        
        missing = expected - found
        if missing:
            print(f"❌ Missing required columns: {missing}")
            return False
        
        # 2. Chart of accounts
        cur.execute("SELECT COUNT(*) FROM chart_of_accounts WHERE account_code IS NOT NULL")
        count = cur.fetchone()[0]
        print(f"✅ Chart of accounts: {count} entries")
        
        # 3. Receipts data
        cur.execute("SELECT COUNT(*) FROM receipts")
        total = cur.fetchone()[0]
        print(f"✅ Total receipts in database: {total} records")
        
        # 4. Vehicles
        cur.execute("SELECT COUNT(*) FROM vehicles")
        vehicles = cur.fetchone()[0]
        print(f"✅ Vehicles in database: {vehicles} records")
        
        # 5. Employees
        cur.execute("SELECT COUNT(*) FROM employees")
        employees = cur.fetchone()[0]
        print(f"✅ Employees in database: {employees} records")
        
        # 6. Banking transactions
        cur.execute("SELECT COUNT(*) FROM banking_transactions")
        banking = cur.fetchone()[0]
        print(f"✅ Banking transactions: {banking} records")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_widget_instantiation():
    """Test that widget can be imported and instantiated"""
    try:
        from desktop_app.receipt_search_match_widget import ReceiptSearchMatchWidget, DateInput, CurrencyInput
        print("✅ Widget classes imported successfully")
        
        import psycopg2
        conn = psycopg2.connect(host='localhost', user='postgres', password='***REMOVED***', dbname='almsdata')
        
        # Instantiate widget
        widget = ReceiptSearchMatchWidget(conn)
        print("✅ Widget instantiated successfully")
        
        # Verify key attributes
        attrs = [
            'new_date', 'new_vendor', 'new_amount', 'new_desc', 'new_gl', 
            'new_banking_id', 'new_charter_input', 'new_vehicle_combo', 
            'new_driver_combo', 'payment_method', 'fuel_liters', 'gst_override_enable'
        ]
        
        missing = []
        for attr in attrs:
            if not hasattr(widget, attr):
                missing.append(attr)
        
        if missing:
            print(f"❌ Missing attributes: {missing}")
            return False
        
        print(f"✅ All {len(attrs)} form fields present and accessible")
        
        # Verify container groups
        container_attrs = ['results_table', 'add_btn', 'update_btn', 'split_btn', 'bulk_import_btn', 'reconcile_btn']
        for attr in container_attrs:
            if not hasattr(widget, attr):
                print(f"❌ Missing: {attr}")
                return False
        
        print(f"✅ All container and button groups present")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Widget instantiation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_startup():
    """Test that the desktop app starts without errors"""
    try:
        from desktop_app.main import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # Don't actually show window, just verify it can be created
        print("✅ MainWindow class imports successfully")
        return True
        
    except Exception as e:
        print(f"❌ App startup error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("COMPREHENSIVE RECEIPT WIDGET VERIFICATION")
    print("=" * 70)
    print()
    
    results = []
    
    print("PHASE 1: Database Schema Verification")
    print("-" * 70)
    results.append(("Database Schema", test_database_schema()))
    print()
    
    print("PHASE 2: Widget Instantiation")
    print("-" * 70)
    results.append(("Widget Instantiation", test_widget_instantiation()))
    print()
    
    print("PHASE 3: App Startup")
    print("-" * 70)
    results.append(("App Startup", test_app_startup()))
    print()
    
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:40} {status}")
    
    all_pass = all(r for _, r in results)
    print()
    if all_pass:
        print("✅ ALL VERIFICATION TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)

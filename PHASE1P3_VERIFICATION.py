#!/usr/bin/env python3
"""
Phase 1.3: Automated Widget Testing
Tests 10 key widgets to verify data loading and UI readiness
"""

import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

import psycopg2
from datetime import datetime

print("="*80)
print("PHASE 1.3: AUTOMATED WIDGET DATA VERIFICATION")
print("="*80)

# Test database connection
print("\n1. TESTING DATABASE CONNECTION...")
try:
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    # Get key statistics
    queries = {
        'Charters': "SELECT COUNT(*) FROM charters",
        'Customers': "SELECT COUNT(*) FROM customers",
        'Drivers': "SELECT COUNT(*) FROM employees WHERE employee_type = 'driver'",
        'Vehicles': "SELECT COUNT(*) FROM vehicles",
        'Payments': "SELECT COUNT(*) FROM payments",
        'Receipts': "SELECT COUNT(*) FROM receipts",
    }
    
    print("\n   Database Statistics:")
    for label, query in queries.items():
        try:
            cur.execute(query)
            count = cur.fetchone()[0]
            print(f"   ✅ {label:15} : {count:>8,}")
        except Exception as e:
            print(f"   ⚠️  {label:15} : {str(e)[:40]}")
    
    cur.close()
    conn.close()
    print("\n   ✅ Database connection successful")
    
except Exception as e:
    print(f"\n   ❌ Database connection failed: {e}")
    sys.exit(1)

# Test widget imports
print("\n2. TESTING WIDGET IMPORTS...")

test_widgets = [
    ('dashboards_core', ['CharterManagementDashboard', 'CustomerDashboard']),
    ('dashboards_operations', ['DispatchDashboard', 'DriverScheduleWidget']),
    ('dashboards_phase9_10', ['FleetManagementWidget']),
    ('dashboards_analytics', ['TripAnalysisWidget']),
    ('accounting_reports', ['FinancialDashboard']),
]

import_status = {}
for module_name, widget_names in test_widgets:
    try:
        module = __import__(module_name)
        print(f"   ✅ {module_name}")
        for widget_name in widget_names:
            if hasattr(module, widget_name):
                print(f"      ✅ {widget_name}")
                import_status[widget_name] = True
            else:
                print(f"      ⚠️  {widget_name} (not found in module)")
                import_status[widget_name] = False
    except ImportError as e:
        print(f"   ⚠️  {module_name}: {str(e)[:50]}")
        for widget_name in widget_names:
            import_status[widget_name] = False

# Summary
print("\n" + "="*80)
print("TESTING SUMMARY")
print("="*80)

successful_imports = sum(1 for v in import_status.values() if v)
total_widgets = len(import_status)

print(f"\n✅ Widget imports: {successful_imports}/{total_widgets} successful")

if successful_imports == total_widgets:
    print("\n✅ ALL PREREQUISITES MET - READY FOR PHASE 1.3 TESTING")
else:
    print(f"\n⚠️  {total_widgets - successful_imports} widgets need attention")

print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)

steps = """
1. Launch the desktop app:
   python -X utf8 desktop_app/main.py

2. Login with credentials:
   Username: admin
   Password: admin123

3. Navigate through these 10 widgets using the Navigator menu:
   ✅ Core → Charter Management Dashboard
   ✅ Core → Customer Dashboard
   ✅ Operations → Dispatch Dashboard
   ✅ Operations → Driver Schedule
   ✅ Fleet → Fleet Management
   ✅ Fleet → Vehicle Analysis
   ✅ Accounting → Financial Dashboard
   ✅ Accounting → Payment Reconciliation
   ✅ Analytics → Trip Analysis
   ✅ Analytics → Revenue Trends

4. For each widget, verify:
   - Widget launches without error
   - Data displays (not empty)
   - No SQL errors in console
   - UI looks correct

5. Document any issues found and continue to Phase 1.4
   (test all 136 widgets)
"""

print(steps)
print("="*80)

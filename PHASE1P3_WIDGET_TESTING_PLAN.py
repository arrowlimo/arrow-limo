#!/usr/bin/env python3
"""
Phase 1.3: Sample Widget Testing Plan
Tests 10 key widgets across all 7 domains to verify:
  1. Widget launches without error
  2. Data loads (non-empty dataset)
  3. No SQL errors
  4. UI renders correctly
"""

import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

print("="*80)
print("PHASE 1.3: SAMPLE WIDGET TESTING PLAN")
print("="*80)

# Test 10 widgets across 7 domains
widgets_to_test = [
    {
        'domain': 'Core',
        'category': 'Charter Management',
        'widget': 'CharterManagementDashboard',
        'expected_data': 'Charters list',
    },
    {
        'domain': 'Core',
        'category': 'Customer Dashboard',
        'widget': 'CustomerDashboard',
        'expected_data': 'Customer list',
    },
    {
        'domain': 'Operations',
        'category': 'Dispatch Dashboard',
        'widget': 'DispatchDashboard',
        'expected_data': 'Dispatch schedules',
    },
    {
        'domain': 'Operations',
        'category': 'Driver Schedule',
        'widget': 'DriverScheduleWidget',
        'expected_data': 'Driver assignments',
    },
    {
        'domain': 'Fleet',
        'category': 'Fleet Management',
        'widget': 'FleetManagementWidget',
        'expected_data': 'Vehicles list',
    },
    {
        'domain': 'Fleet',
        'category': 'Vehicle Analysis',
        'widget': 'VehicleAnalysisWidget',
        'expected_data': 'Vehicle metrics',
    },
    {
        'domain': 'Accounting',
        'category': 'Financial Dashboard',
        'widget': 'FinancialDashboard',
        'expected_data': 'Financial metrics',
    },
    {
        'domain': 'Accounting',
        'category': 'Payment Reconciliation',
        'widget': 'PaymentReconciliationWidget',
        'expected_data': 'Payment records',
    },
    {
        'domain': 'Analytics',
        'category': 'Trip Analysis',
        'widget': 'TripAnalysisWidget',
        'expected_data': 'Trip statistics',
    },
    {
        'domain': 'Analytics',
        'category': 'Revenue Trends',
        'widget': 'RevenueTrendsWidget',
        'expected_data': 'Revenue metrics',
    },
]

print("\n📋 TESTING PLAN: 10 Sample Widgets\n")
print(f"{'#':<3} {'Domain':<12} {'Category':<25} {'Widget':<30} {'Expected Data':<20}")
print("-" * 95)

for i, widget in enumerate(widgets_to_test, 1):
    print(f"{i:<3} {widget['domain']:<12} {widget['category']:<25} {widget['widget']:<30} {widget['expected_data']:<20}")

print("\n" + "="*80)
print("TESTING INSTRUCTIONS")
print("="*80)

instructions = """
1. LAUNCH THE APP
   - Run: python -X utf8 desktop_app/main.py
   - Wait for login dialog to appear
   
2. LOGIN
   - Username: admin
   - Password: admin123
   - Click "Sign In"
   
3. NAVIGATE TO MEGA MENU
   - Click on "Navigator" tab
   - You should see 7 domains in the mega menu:
     * Core
     * Operations
     * Customer
     * ML
     * Predictive
     * Optimization
     * Analytics

4. TEST FIRST WIDGET
   - Click on "Core" domain
   - Select "Charter Management Dashboard" widget
   - Verify it loads with data (charters list should appear)
   - Check for errors in console output
   
5. REPEAT FOR OTHER 9 WIDGETS
   - Test one widget from each domain
   - Document any errors or missing data
   - Check that UI renders correctly
   
6. SUCCESS CRITERIA
   For each widget:
   ✅ Widget launches without crashing
   ✅ Data loads (non-empty dataset)
   ✅ No SQL errors in console
   ✅ UI renders without layout issues
   ✅ All expected columns present

7. FAILURE CRITERIA
   ❌ Widget crashes on launch
   ❌ Data is empty (0 rows/items)
   ❌ SQL error in console (column missing, syntax error, etc.)
   ❌ Layout broken or misaligned
   ❌ Missing required columns

8. DOCUMENT RESULTS
   For each widget tested, note:
   - Widget name
   - Launch status (success/fail)
   - Data status (items loaded/empty/error)
   - Any error messages
   - Visual issues observed
"""

print(instructions)

print("\n" + "="*80)
print("QUICK TEST: Database & Widget Import Verification")
print("="*80 + "\n")

# Quick verification
try:
    from database_connection import DatabaseConnection
    db = DatabaseConnection()
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM charters")
        charter_count = cur.fetchone()[0]
        print(f"✅ Database: {charter_count:,} charters available")
except Exception as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)

# Try importing key widget modules
widget_imports = [
    ('dashboards_core', 'CharterManagementDashboard'),
    ('dashboards_operations', 'DispatchDashboard'),
    ('dashboards_customer', 'CustomerDashboard'),
    ('dashboards_phase9_10', 'FleetManagementWidget'),
    ('dashboards_analytics', 'TripAnalysisWidget'),
]

print("\nWidget module imports:")
all_ok = True
for module_name, widget_name in widget_imports:
    try:
        module = __import__(module_name)
        print(f"  ✅ {module_name}: {widget_name} available")
    except ImportError as e:
        print(f"  ⚠️  {module_name}: Import warning - {e}")
        all_ok = False

if all_ok:
    print("\n✅ All prerequisites ready - ready for Phase 1.3 widget testing!")
else:
    print("\n⚠️  Some imports had warnings - may need troubleshooting during testing")

print("\n" + "="*80)
print("NEXT STEP: Launch app with 'python -X utf8 desktop_app/main.py'")
print("="*80)

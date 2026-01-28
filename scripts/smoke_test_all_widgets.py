#!/usr/bin/env python3
"""
SMOKE TEST: Quick functional test of all desktop app widgets and reports.
Tests that each widget can initialize without crashing.
"""

import sys
import os
sys.path.insert(0, 'l:\\limo')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
import psycopg2
import traceback

# Initialize QApplication for testing
app = QApplication(sys.argv)

# Database connection
def get_db():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

print("=" * 70)
print("SMOKE TEST: Desktop App Widgets & Reports")
print("=" * 70)

test_results = []

# Test widget initializations
test_cases = [
    {
        'name': 'Fleet Management',
        'module': 'desktop_app.dashboards_phase1',
        'class': 'FleetManagementWidget',
        'needs_db': True
    },
    {
        'name': 'Driver Performance',
        'module': 'desktop_app.dashboards_phase2',
        'class': 'DriverPerformanceWidget',
        'needs_db': True
    },
    {
        'name': 'Financial Dashboard',
        'module': 'desktop_app.dashboards_phase3',
        'class': 'FinancialDashboardWidget',
        'needs_db': True
    },
    {
        'name': 'Payment Reconciliation',
        'module': 'desktop_app.dashboards_phase3',
        'class': 'PaymentReconciliationWidget',
        'needs_db': True
    },
    {
        'name': 'Profit & Loss Report',
        'module': 'desktop_app.dashboards_phase4_5_6',
        'class': 'ProfitLossReportWidget',
        'needs_db': True
    },
    {
        'name': 'Cash Flow Report',
        'module': 'desktop_app.dashboards_phase4_5_6',
        'class': 'CashFlowReportWidget',
        'needs_db': True
    },
    {
        'name': 'Vehicle Fleet Cost',
        'module': 'desktop_app.dashboards_phase4_5_6',
        'class': 'VehicleFleetCostAnalysisWidget',
        'needs_db': True
    },
    {
        'name': 'Fuel Efficiency',
        'module': 'desktop_app.dashboards_phase7',
        'class': 'FuelEfficiencyWidget',
        'needs_db': True
    },
    {
        'name': 'Fleet Age Analysis',
        'module': 'desktop_app.dashboards_phase8',
        'class': 'FleetAgeAnalysisWidget',
        'needs_db': True
    },
    {
        'name': 'Driver Pay Analysis',
        'module': 'desktop_app.dashboards_phase9',
        'class': 'DriverPayAnalysisWidget',
        'needs_db': True
    },
    {
        'name': 'Driver Schedule',
        'module': 'desktop_app.dashboards_phase10',
        'class': 'DriverScheduleWidget',
        'needs_db': True
    },
]

passed = 0
failed = 0

for test_case in test_cases:
    try:
        print(f"\n▶️  Testing: {test_case['name']}")
        
        # Import module
        module = __import__(test_case['module'], fromlist=[test_case['class']])
        widget_class = getattr(module, test_case['class'])
        
        # Get database if needed
        db = get_db() if test_case['needs_db'] else None
        
        # Initialize widget
        if test_case['needs_db']:
            widget = widget_class(db)
        else:
            widget = widget_class()
        
        # Show it briefly to trigger any rendering errors
        widget.show()
        app.processEvents()
        widget.hide()
        
        print(f"   ✅ PASS: {test_case['name']} initialized successfully")
        test_results.append({
            'name': test_case['name'],
            'status': 'PASS',
            'error': None
        })
        passed += 1
        
        if db:
            db.close()
        
    except Exception as e:
        error_msg = str(e)[:100]  # First 100 chars of error
        print(f"   ❌ FAIL: {test_case['name']}")
        print(f"      Error: {error_msg}")
        print(f"      {traceback.format_exc()[:200]}")
        test_results.append({
            'name': test_case['name'],
            'status': 'FAIL',
            'error': error_msg
        })
        failed += 1

# Summary
print("\n" + "=" * 70)
print("SMOKE TEST SUMMARY")
print("=" * 70)
print(f"\n✅ PASSED: {passed}/{len(test_cases)}")
print(f"❌ FAILED: {failed}/{len(test_cases)}")

if failed > 0:
    print(f"\nFailed widgets:")
    for result in test_results:
        if result['status'] == 'FAIL':
            print(f"  - {result['name']}: {result['error']}")

print("\n" + "=" * 70)
if failed == 0:
    print("🎉 ALL WIDGETS PASSED SMOKE TEST!")
else:
    print(f"⚠️  {failed} widget(s) need fixes")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)

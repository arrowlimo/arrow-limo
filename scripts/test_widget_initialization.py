#!/usr/bin/env python3
"""
Test all desktop app widgets for initialization crashes
"""
import sys
import traceback
from pathlib import Path

# Test basic imports
print("Testing all widget imports and initialization...\n")

widgets_to_test = [
    ("FleetManagement", "desktop_app.dashboards", "FleetManagementWidget"),
    ("DriverPerformance", "desktop_app.dashboards", "DriverPerformanceWidget"),
    ("FinancialDashboard", "desktop_app.dashboards", "FinancialDashboardWidget"),
    ("PaymentReconciliation", "desktop_app.dashboards", "PaymentReconciliationWidget"),
    ("ProfitLossReport", "desktop_app.dashboards", "ProfitLossReportWidget"),
    ("CashFlowReport", "desktop_app.dashboards_phase4_5_6", "CashFlowReportWidget"),
    ("VehicleFleetCost", "desktop_app.dashboards_phase4_5_6", "VehicleFleetCostAnalysisWidget"),
    ("FuelEfficiency", "desktop_app.dashboards_phase4_5_6", "FuelEfficiencyTrackingWidget"),
    ("FleetAgeAnalysis", "desktop_app.dashboards_phase4_5_6", "FleetAgeAnalysisWidget"),
    ("DriverPayAnalysis", "desktop_app.dashboards_phase4_5_6", "DriverPayAnalysisWidget"),
    ("DriverSchedule", "desktop_app.dashboards_phase4_5_6", "DriverScheduleManagementWidget"),
    ("AdminManagement", "desktop_app.admin_management_widget", "AdminManagementWidget"),
]

import psycopg2

# Create a mock DB object that widgets expect
class MockDB:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                host='localhost',
                database='almsdata',
                user='postgres',
                password='***REMOVED***'
            )
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            self.conn = None
    
    def cursor(self):
        if self.conn:
            return self.conn.cursor()
        return None
    
    def close(self):
        if self.conn:
            self.conn.close()

passed = 0
failed = 0
errors = []

for name, module_name, class_name in widgets_to_test:
    try:
        # Import the module
        module = __import__(module_name, fromlist=[class_name])
        widget_class = getattr(module, class_name)
        
        # Try to instantiate (without showing GUI)
        db = MockDB()
        if db.conn:
            widget = widget_class(db.conn)
            print(f"✅ {name}: Initialized successfully")
            passed += 1
            db.close()
        else:
            print(f"⚠️  {name}: Skipped (no DB)")
            
    except Exception as e:
        print(f"❌ {name}: {str(e)[:80]}")
        errors.append((name, traceback.format_exc()))
        failed += 1

print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'='*60}")

if errors:
    print("\nDetailed Errors:\n")
    for name, error in errors:
        print(f"--- {name} ---")
        print(error[:500])
        print()

sys.exit(0 if failed == 0 else 1)

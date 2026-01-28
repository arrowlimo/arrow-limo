#!/usr/bin/env python3
"""
Quick diagnostic script to find which widget tabs are crashing
Run each widget in isolation to identify the problematic ones
"""
import sys
import os
import traceback

# Add to path
sys.path.insert(0, os.path.dirname(__file__))

def test_widget_import(widget_name, module_name, class_name):
    """Test a single widget import and instantiation"""
    try:
        module = __import__(module_name, fromlist=[class_name])
        widget_class = getattr(module, class_name)
        # Just check the class exists, don't instantiate
        return True, "✅ Imports OK"
    except Exception as e:
        return False, f"❌ Import failed: {str(e)[:60]}"

# List of all widgets in the tabs
widgets = [
    ("CashFlowReport", "dashboards_phase4_5_6", "CashFlowReportWidget"),
    ("VehicleFleetCost", "dashboards_phase4_5_6", "VehicleFleetCostAnalysisWidget"),
    ("FuelEfficiency", "dashboards_phase4_5_6", "FuelEfficiencyTrackingWidget"),
    ("VehicleUtilization", "dashboards_phase4_5_6", "VehicleUtilizationWidget"),
    ("FleetAgeAnalysis", "dashboards_phase4_5_6", "FleetAgeAnalysisWidget"),
    ("DriverPayAnalysis", "dashboards_phase4_5_6", "DriverPayAnalysisWidget"),
    ("EmployeePerformance", "dashboards_phase4_5_6", "EmployeePerformanceMetricsWidget"),
    ("PayrollTaxCompliance", "dashboards_phase4_5_6", "PayrollTaxComplianceWidget"),
    ("DriverSchedule", "dashboards_phase4_5_6", "DriverScheduleManagementWidget"),
]

print("="*70)
print("WIDGET IMPORT DIAGNOSTICS")
print("="*70)

passed = 0
failed = 0

for name, module, class_n in widgets:
    success, msg = test_widget_import(name, module, class_n)
    print(f"{msg} - {name} ({module})")
    if success:
        passed += 1
    else:
        failed += 1

print("\n" + "="*70)
print(f"RESULT: {passed} passed, {failed} failed")
print("="*70)

if failed > 0:
    print("\n⚠️ Some widgets have import errors. These will crash tabs when opened.")
else:
    print("\n✅ All widget imports OK. Issues likely in tab creation methods or database queries.")

sys.exit(0)

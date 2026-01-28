#!/usr/bin/env python
"""Count all widget classes available in the dashboard modules"""

import sys
import re
import os

sys.path.insert(0, r'l:\limo\desktop_app')

# Import all dashboard modules
try:
    import dashboards_core
    import dashboards_operations
    import dashboards_predictive
    import dashboards_optimization
    import dashboards_customer
    import dashboards_analytics
    import dashboards_ml
    
    all_modules = [
        ("dashboards_core", dashboards_core),
        ("dashboards_operations", dashboards_operations),
        ("dashboards_predictive", dashboards_predictive),
        ("dashboards_optimization", dashboards_optimization),
        ("dashboards_customer", dashboards_customer),
        ("dashboards_analytics", dashboards_analytics),
        ("dashboards_ml", dashboards_ml),
    ]
    
    print("=" * 60)
    print("AVAILABLE WIDGET CLASSES BY MODULE")
    print("=" * 60)
    
    total_widgets = 0
    for module_name, module in all_modules:
        # Get all classes ending with "Widget"
        widgets = [name for name in dir(module) if name.endswith('Widget') and not name.startswith('_')]
        print(f"\n{module_name:30} ({len(widgets)} widgets)")
        for widget in sorted(widgets):
            print(f"  - {widget}")
        total_widgets += len(widgets)
    
    print("\n" + "=" * 60)
    print(f"TOTAL WIDGET CLASSES: {total_widgets}")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error importing modules: {e}")
    import traceback
    traceback.print_exc()

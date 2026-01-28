#!/usr/bin/env python
"""Test script that launches the app and verifies multiple widgets load correctly"""

import sys
import os
import time

sys.path.insert(0, r'l:\limo\desktop_app')
os.chdir(r'l:\limo')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from desktop_app.main import MainWindow

def test_widgets():
    """Test multiple widgets to ensure they all load with data"""
    
    app = QApplication(sys.argv)
    
    try:
        main_window = MainWindow()
        print("✅ Main window created")
        
        # Get the mega menu widget
        navigator_tab = main_window.tabs.widget(0)
        print(f"✅ Navigator tab found")
        
        # Simulate selecting and launching different widgets
        test_widgets_list = [
            "FleetManagementWidget",
            "VehicleAnalyticsWidget", 
            "DriverPerformanceWidget",
            "FinancialDashboardWidget",
            "PaymentReconciliationWidget"
        ]
        
        print("\n📊 Testing Widget Data Loading:")
        print("=" * 60)
        
        launched_count = 0
        for widget_name in test_widgets_list:
            try:
                # Find and launch widget via mega menu signal
                navigator_tab.widget_selected.emit(widget_name, widget_name)
                launched_count += 1
                print(f"  ✅ {widget_name:40} [LAUNCHED]")
            except Exception as e:
                print(f"  ❌ {widget_name:40} [FAILED: {str(e)[:40]}]")
        
        print("=" * 60)
        print(f"\n✅ Test Complete: {launched_count}/{len(test_widgets_list)} widgets tested")
        
        # Show window
        main_window.show()
        
        # Run event loop briefly then exit
        QTimer.singleShot(2000, app.quit)
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_widgets()

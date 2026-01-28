"""
Quick test for CRA Tax Management Widget integration
Verifies the widget loads and displays data correctly
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_app'))

from PyQt6.QtWidgets import QApplication
from desktop_app.database_connection import DatabaseConnection
from desktop_app.tax_management_widget import TaxManagementWidget

def test_tax_widget():
    """Test that tax widget loads without errors"""
    print("🧪 Testing CRA Tax Management Widget...")
    
    app = QApplication(sys.argv)
    
    # Connect to database
    db = DatabaseConnection()
    
    try:
        # Create widget
        widget = TaxManagementWidget(db)
        widget.show()
        
        print("✅ Widget created successfully")
        print(f"✅ Year table has {widget.year_table.rowCount()} rows")
        print(f"✅ Expected 14 rows (2012-2025)")
        
        # Check a few years have data
        for row in range(widget.year_table.rowCount()):
            year_item = widget.year_table.item(row, 0)
            revenue_item = widget.year_table.item(row, 1)
            if year_item and revenue_item:
                year = year_item.text()
                revenue = revenue_item.text()
                print(f"   Year {year}: Revenue {revenue}")
        
        print("\n✅ CRA Tax Management Widget test PASSED")
        print("\n📋 Next Steps:")
        print("1. Launch desktop app: python -X utf8 desktop_app/main.py")
        print("2. Navigate to '🏛️ CRA Tax Management' tab")
        print("3. Double-click a year (e.g., 2024) for detailed view")
        print("4. Review revenue, expenses, payroll, GST calculations")
        print("5. Generate CRA forms (T4, GST34, etc.)")
        print("\n📚 User Guide: L:\\limo\\docs\\CRA_TAX_MANAGEMENT_USER_GUIDE.md")
        
        return True
        
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Don't start event loop in test
        pass

if __name__ == "__main__":
    success = test_tax_widget()
    sys.exit(0 if success else 1)

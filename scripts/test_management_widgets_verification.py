#!/usr/bin/env python3
"""
Test the updated management widgets with verification tracking
"""
import sys
import psycopg2
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

# Import the updated widgets
sys.path.insert(0, 'l:/limo/desktop_app')
from manage_receipts_widget import ManageReceiptsWidget
from manage_banking_widget import ManageBankingWidget
from manage_cash_box_widget import ManageCashBoxWidget

def test_widgets():
    """Test all three management widgets"""
    
    # Connect to database
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create main window with tabs
    window = QMainWindow()
    window.setWindowTitle("Management Widgets Test - With Verification")
    window.setGeometry(100, 100, 1400, 800)
    
    tabs = QTabWidget()
    
    # Add widgets
    try:
        receipts_widget = ManageReceiptsWidget(conn)
        tabs.addTab(receipts_widget, "📋 Receipts (Updated)")
        print("✅ Receipts widget loaded")
    except Exception as e:
        print(f"❌ Receipts widget error: {e}")
    
    try:
        banking_widget = ManageBankingWidget(conn)
        tabs.addTab(banking_widget, "🏦 Banking")
        print("✅ Banking widget loaded")
    except Exception as e:
        print(f"❌ Banking widget error: {e}")
    
    try:
        cashbox_widget = ManageCashBoxWidget(conn)
        tabs.addTab(cashbox_widget, "💰 Cash Box")
        print("✅ Cash Box widget loaded")
    except Exception as e:
        print(f"❌ Cash Box widget error: {e}")
    
    window.setCentralWidget(tabs)
    window.show()
    
    print("\n" + "="*60)
    print("TEST INSTRUCTIONS:")
    print("="*60)
    print("1. Check Receipts tab - should have 'Verified' column")
    print("2. Try filtering by 'Verified' dropdown")
    print("3. Verify stats show in results label")
    print("4. Check color coding: Green=Verified, Yellow=Unverified")
    print("="*60)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    test_widgets()

#!/usr/bin/env python
"""Test script to isolate ReceiptSearchMatchWidget crash"""
import sys
import os
from pathlib import Path

# Add paths
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
for path_candidate in (current_dir, project_root):
    if path_candidate not in sys.path:
        sys.path.insert(0, path_candidate)

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget
from PyQt6.QtCore import Qt

# Import database and widget
sys.path.insert(0, 'L:\\limo\\desktop_app')
sys.path.insert(0, 'L:\\limo\\modern_backend')
try:
    from database import DatabaseConnection
except ImportError:
    from modern_backend.app.database import DatabaseConnection
from desktop_app.receipt_search_match_widget import ReceiptSearchMatchWidget

def main():
    print("Starting test app...", flush=True)
    app = QApplication(sys.argv)
    
    print("Creating MainWindow...", flush=True)
    window = QMainWindow()
    window.setWindowTitle("ReceiptSearchMatchWidget Test")
    window.setGeometry(50, 50, 1200, 800)
    
    print("Creating database connection...", flush=True)
    try:
        db = DatabaseConnection()
    except Exception as e:
        print(f"DB connection error: {e}", flush=True)
        sys.exit(1)
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Create a tab widget with parent reference
    print("Creating parent tab widget...", flush=True)
    tabs = QTabWidget()
    
    print("Creating ReceiptSearchMatchWidget...", flush=True)
    try:
        search_widget = ReceiptSearchMatchWidget(db.conn, parent_tab_widget=tabs)
        print("Successfully created ReceiptSearchMatchWidget!", flush=True)
        tabs.addTab(search_widget, "Search")
    except SystemExit as se:
        print(f"SystemExit: {se}", flush=True)
        raise
    except Exception as e:
        print(f"Error creating ReceiptSearchMatchWidget: {e}", flush=True)
        import traceback
        traceback.print_exc()
        error_label = QLabel(f"Error: {e}")
        tabs.addTab(error_label, "Error")
    
    layout.addWidget(tabs)
    window.setCentralWidget(central)
    window.show()
    
    print("Entering event loop...", flush=True)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

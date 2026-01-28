#!/usr/bin/env python
"""Standalone test of Fleet Management Widget"""

import sys
import os
sys.path.insert(0, r'l:\limo\desktop_app')
os.chdir(r'l:\limo\desktop_app')

import psycopg2
from PyQt6.QtWidgets import QApplication, QMainWindow
from dashboard_classes import FleetManagementWidget

class DatabaseConnection:
    """PostgreSQL database connection manager"""
    def __init__(self):
        self.conn = psycopg2.connect(
            host="localhost", port="5432", database="almsdata",
            user="postgres", password="***REMOVED***"
        )
        self.conn.autocommit = False
    
    def get_cursor(self):
        return self.conn.cursor()
    
    def commit(self):
        self.conn.commit()
    
    def rollback(self):
        self.conn.rollback()
    
    def close(self):
        self.conn.close()

# Create app
app = QApplication(sys.argv)
db = DatabaseConnection()

# Create main window
main_window = QMainWindow()
main_window.setWindowTitle("Fleet Management Widget Test")
main_window.setGeometry(100, 100, 800, 500)

# Create and add widget
widget = FleetManagementWidget(db)
main_window.setCentralWidget(widget)

# Show
main_window.show()
print("✅ Widget created and displayed")

# Run
sys.exit(app.exec())

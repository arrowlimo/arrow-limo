#!/usr/bin/env python
"""Test app with proper setup and wait time"""

import sys
import os

# Setup paths  
sys.path.insert(0, r'l:\limo\desktop_app')
os.chdir(r'l:\limo')

# Now import and run the main app
from PyQt6.QtWidgets import QApplication
from desktop_app.main import MainWindow

print("Starting Arrow Limousine Desktop App...")
print("=" * 60)

app = QApplication(sys.argv)

try:
    main_window = MainWindow()
    print("✅ Main window created successfully")
    print("✅ Navigator tab should be available")
    print("=" * 60)
    main_window.show()
    sys.exit(app.exec())
except Exception as e:
    print(f"❌ Error starting app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

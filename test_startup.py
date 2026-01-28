#!/usr/bin/env python3
"""Test MainWindow startup step by step"""
import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

print("1. Importing QApplication...")
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
print("   ✅ QApplication created")

print("2. Importing MainWindow...")
from main import MainWindow
print("   ✅ MainWindow imported")

print("3. Creating MainWindow instance...")
try:
    window = MainWindow()
    print("   ✅ MainWindow created successfully!")
    print("4. Showing window...")
    window.show()
    print("   ✅ Window shown")
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All tests passed!")
print("Exiting...")
sys.exit(0)

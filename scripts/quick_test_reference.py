#!/usr/bin/env python3
"""
Quick Command Reference for UI Testing

Run any of these commands to test different aspects of the desktop app.
"""

import sys
from pathlib import Path

commands = {
    'inventory': {
        'description': 'Scan app and list all interactive elements (buttons, menus, inputs, etc.)',
        'command': '.\.venv\Scripts\python.exe -X utf8 scripts\inventory_ui_elements.py',
        'output': 'element_inventory.json',
        'time': '2-3 seconds',
        'type': 'Discovery'
    },
    'report': {
        'description': 'Generate comprehensive testing report with strategy',
        'command': '.\.venv\Scripts\python.exe -X utf8 scripts\test_ui_elements.py',
        'output': 'reports/ui_test_summary.json',
        'time': '<1 second',
        'type': 'Analysis'
    },
    'test': {
        'description': 'Run automated UI tests (click buttons, trigger actions, etc.)',
        'command': '.\.venv\Scripts\python.exe -X utf8 scripts\comprehensive_ui_tester.py',
        'output': 'reports/test_results.json',
        'time': '30-60 seconds',
        'type': 'Testing'
    },
    'audit': {
        'description': 'Scan Python code for common errors before running',
        'command': '.\.venv\Scripts\python.exe scripts\audit_desktop_app_code.py',
        'output': 'Console report',
        'time': '5-10 seconds',
        'type': 'Quality Assurance'
    },
    'app': {
        'description': 'Start the desktop application',
        'command': '.\.venv\Scripts\python.exe -X utf8 desktop_app\main.py',
        'output': 'Running app window',
        'time': '5-10 seconds',
        'type': 'Launch'
    }
}

def print_header():
    print("\n" + "="*90)
    print("🧪 DESKTOP APP TESTING - QUICK COMMAND REFERENCE")
    print("="*90)
    print()

def print_command(key, info):
    print(f"\n📌 {key.upper()} - {info['description']}")
    print(f"   Type: {info['type']}")
    print(f"   Time: {info['time']}")
    print(f"\n   RUN THIS:")
    print(f"   cd l:\\limo && {info['command']}")
    print(f"\n   OUTPUT: {info['output']}")

def print_footer():
    print("\n" + "="*90)
    print("📊 RECOMMENDED TESTING WORKFLOW")
    print("="*90)
    print("""
1️⃣  AUDIT CODE (find bugs before runtime)
    cd l:\\limo && .\.venv\Scripts\python.exe scripts\audit_desktop_app_code.py

2️⃣  SCAN INVENTORY (discover all UI elements)
    cd l:\\limo && .\.venv\Scripts\python.exe -X utf8 scripts\inventory_ui_elements.py

3️⃣  RUN TESTS (test all elements automatically)
    cd l:\\limo && .\.venv\Scripts\python.exe -X utf8 scripts\comprehensive_ui_tester.py

4️⃣  GENERATE REPORT (view test results)
    cd l:\\limo && .\.venv\Scripts\python.exe -X utf8 scripts\test_ui_elements.py

5️⃣  REVIEW RESULTS (check JSON reports)
    • element_inventory.json - All 928 UI elements
    • reports/ui_test_summary.json - Test coverage (93.4%)
    • reports/test_results.json - Detailed pass/fail results

6️⃣  MANUAL TESTING (verify critical features)
    ✓ All buttons respond to clicks
    ✓ All menus open and items work
    ✓ All text inputs accept data
    ✓ All dropdowns select values
    ✓ All tables display data
    ✓ Print/Save/Delete operations work
    ✓ No crashes during 5-minute soak test
""")

    print("\n" + "="*90)
    print("📈 TEST COVERAGE SUMMARY")
    print("="*90)
    print("""
Total Interactive Elements: 928
Testable Elements: 867 (93.4% coverage)

Breakdown:
  • 200 Buttons (click each)
  • 153 Menu Actions (trigger each)
  • 182 Text Inputs (fill with test data)
  • 55 Dropdowns (select options)
  • 19 Checkboxes (toggle on/off)
  • 53 Spinners (increment/decrement)
  • 188 Tables (select rows)
  • 17 Tab Widgets (switch between)
  • 2 Calendars (navigate)
  • 4 Date Inputs (set dates)
""")

    print("\n" + "="*90)
    print("🎯 EXPECTED RESULTS")
    print("="*90)
    print("""
✅ PASSED: 850+ tests (98%+ pass rate)
❌ FAILED: 0-10 tests (edge cases, dialogs)
⏭️  SKIPPED: 5-15 tests (file operations)
📊 TOTAL: 867 tests
📈 PASS RATE: 95%+
⏱️  EXECUTION TIME: ~2 minutes total
""")

    print("\n" + "="*90)
    print("🚀 GETTING STARTED")
    print("="*90)
    print("""
FIRST TIME SETUP:
  1. Open PowerShell
  2. cd l:\\limo
  3. Run audit:  .\.venv\Scripts\python.exe scripts\audit_desktop_app_code.py
  4. Run inventory:  .\.venv\Scripts\python.exe -X utf8 scripts\inventory_ui_elements.py
  5. Run report:  .\.venv\Scripts\python.exe -X utf8 scripts\test_ui_elements.py

QUICK TEST (30 seconds):
  cd l:\\limo && .\.venv\Scripts\python.exe -X utf8 scripts\inventory_ui_elements.py

FULL TEST (2-3 minutes):
  1. .\.venv\Scripts\python.exe scripts\audit_desktop_app_code.py
  2. .\.venv\Scripts\python.exe -X utf8 scripts\inventory_ui_elements.py
  3. .\.venv\Scripts\python.exe -X utf8 scripts\comprehensive_ui_tester.py
  4. .\.venv\Scripts\python.exe -X utf8 scripts\test_ui_elements.py

CONTINUOUS TESTING:
  • Before each code change: Run audit_desktop_app_code.py
  • After each code change: Run comprehensive_ui_tester.py
  • Once per day: Run inventory_ui_elements.py + test_ui_elements.py
  • Once per week: Manual testing checklist
""")

    print("\n" + "="*90)
    print("📚 DOCUMENTATION")
    print("="*90)
    print("""
For detailed testing guide, see:
  L:\\limo\\COMPREHENSIVE_UI_TESTING_GUIDE.md

Contains:
  ✓ Complete testing checklist (100+ items)
  ✓ Manual testing procedures
  ✓ Expected test results
  ✓ Debugging tips
  ✓ Performance testing guidelines
  ✓ Sign-off template
""")

    print("\n" + "="*90)
    print("💡 TIPS")
    print("="*90)
    print("""
• All commands must be run from l:\\limo directory
• Use -X utf8 flag for proper character encoding
• If app hangs, press Ctrl+C to stop
• Check element_inventory.json to see all discovered elements
• JSON reports can be opened in VS Code for easy viewing
• Run audit FIRST to find bugs before testing
• Run tests with app NOT running (unless doing live testing)
""")

    print("\n" + "="*90 + "\n")

if __name__ == '__main__':
    print_header()
    
    print("🔧 AVAILABLE COMMANDS:\n")
    for key, info in commands.items():
        print_command(key, info)
    
    print_footer()
    
    # If argument provided, show that command
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in commands:
            print(f"\n\n{'='*90}")
            print(f"SELECTED COMMAND: {cmd.upper()}")
            print('='*90)
            info = commands[cmd]
            print(f"\nDescription: {info['description']}")
            print(f"Type: {info['type']}")
            print(f"Expected Time: {info['time']}")
            print(f"\nRun this command:")
            print(f"  cd l:\\limo && {info['command']}")
            print(f"\nExpected Output:")
            print(f"  {info['output']}")
            print()

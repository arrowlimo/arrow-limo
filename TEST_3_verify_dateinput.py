#!/usr/bin/env python
"""
TEST 3: Verify DateInput class functionality
Task: Test flexible date parsing with 8+ format support
Expected: Accepts YYYY-MM-DD, MM/DD/YYYY, Jan 01 2012, t (today), y (yesterday)
"""
import sys
sys.path.insert(0, 'L:\\limo')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from desktop_app.receipt_search_match_widget import DateInput
from PyQt6.QtCore import QDate
import datetime

app = QApplication([])

print("=" * 80)
print("TEST 3: DATEINPUT CLASS FUNCTIONALITY")
print("=" * 80)
print()

test_cases = [
    ("01/15/2025", True, "MM/DD/YYYY format"),
    ("2025-01-15", True, "YYYY-MM-DD format"),
    ("Jan 15 2025", True, "Text month format"),
    ("January 15 2025", True, "Full month name"),
    ("15 Jan 2025", True, "DD Month YYYY format"),
    ("t", True, "Today shortcut"),
    ("y", True, "Yesterday shortcut"),
    ("1/1/2020", True, "Single digit month/day"),
    ("2025/01/15", True, "YYYY/MM/DD format"),
    ("invalid-date", False, "Invalid format"),
]

print(f"{'Input':<25} {'Expected':<10} {'Result':<10} {'Color Match':<15} {'Test Description'}")
print("-" * 120)

passed = 0
failed = 0

for input_text, should_be_valid, description in test_cases:
    date_input = DateInput()
    date_input.setText(input_text)
    
    # DateInput uses date() method, not toDate()
    try:
        parsed_date = date_input.date()
        is_valid = parsed_date.isValid() if parsed_date else False
    except:
        is_valid = False
    
    # Determine if test passed
    if should_be_valid:
        test_pass = is_valid
        expected_str = "Valid"
        result_str = "Valid" if is_valid else "Invalid"
    else:
        test_pass = not is_valid
        expected_str = "Invalid"
        result_str = "Invalid" if not is_valid else "Valid"
    
    status = "✅ PASS" if test_pass else "❌ FAIL"
    color_match = "Green" if is_valid else "Red" if not is_valid else "Unknown"
    
    print(f"{input_text:<25} {expected_str:<10} {result_str:<10} {color_match:<15} {description}")
    
    if test_pass:
        passed += 1
    else:
        failed += 1

print()
print("=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)
print(f"✅ Tests Passed: {passed}/{len(test_cases)}")
if failed > 0:
    print(f"❌ Tests Failed: {failed}/{len(test_cases)}")

print()
print("-" * 80)
print("Format Support Verification:")
print("-" * 80)

date_input = DateInput()

# Test each supported format
formats_to_test = [
    ("01/15/2025", "MM/DD/YYYY"),
    ("2025-01-15", "YYYY-MM-DD"),
    ("Jan 15 2025", "Mon DD YYYY"),
    ("15 Jan 2025", "DD Mon YYYY"),
    ("t", "Today"),
    ("y", "Yesterday"),
]

for test_input, format_name in formats_to_test:
    date_input = DateInput()
    date_input.setText(test_input)
    parsed = date_input.date()
    status = "✅" if parsed and parsed.isValid() else "❌"
    print(f"{status} {format_name:<20} accepts '{test_input}'")

print()
print("=" * 80)

if failed == 0:
    print("✅ TEST 3 PASSED: DateInput supports all required formats")
else:
    print(f"❌ TEST 3 FAILED: {failed} format(s) not supported")

print("=" * 80)

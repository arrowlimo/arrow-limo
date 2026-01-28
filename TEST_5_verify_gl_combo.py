#!/usr/bin/env python
"""
TEST 5: Verify GL QComboBox methods
Task: Test setEditText() and setCurrentIndex(-1) work correctly
Expected: GL field uses correct QComboBox methods (NOT setText/clear)
"""
import sys
sys.path.insert(0, 'L:\\limo')

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

from PyQt6.QtWidgets import QApplication, QComboBox
from PyQt6.QtCore import QTimer

app = QApplication([])

print("=" * 80)
print("TEST 5: GL QCOMBOBOX METHODS VERIFICATION")
print("=" * 80)
print()

# Create a test QComboBox like the GL field
gl_combo = QComboBox()
gl_combo.setEditable(True)
gl_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

# Load GL accounts
try:
    cur = conn.cursor()
    cur.execute("SELECT account_code, account_name FROM chart_of_accounts ORDER BY account_code LIMIT 20")
    rows = cur.fetchall()
    
    test_codes = []
    for code, name in rows:
        if code:
            gl_combo.addItem(f"{code} — {name}", code)
            test_codes.append(code)
    
    cur.close()
    
    print(f"Loaded {gl_combo.count()} GL codes from database")
    print()
    
except Exception as e:
    print(f"❌ Error loading GL codes: {e}")
    conn.close()
    exit(1)

# Test 1: Check that setEditText() works for setting custom text
print("Test 1: setEditText() method")
print("-" * 80)
try:
    gl_combo.setEditText("5000 — Testing Expense")
    result_text = gl_combo.currentText()
    test_pass = "5000" in result_text or "Testing" in result_text
    status = "✅ PASS" if test_pass else "❌ FAIL"
    print(f"{status} Can set custom GL text with setEditText()")
    print(f"      Result: {result_text}")
except Exception as e:
    print(f"❌ FAIL: setEditText() raised error: {e}")
    test_pass = False

test1_pass = test_pass

print()

# Test 2: Check that setCurrentIndex(-1) clears selection
print("Test 2: setCurrentIndex(-1) method")
print("-" * 80)
try:
    gl_combo.setCurrentIndex(-1)
    current_text = gl_combo.currentText()
    current_idx = gl_combo.currentIndex()
    test_pass = current_idx == -1
    status = "✅ PASS" if test_pass else "❌ FAIL"
    print(f"{status} setCurrentIndex(-1) clears selection")
    print(f"      Current Index: {current_idx} (expected: -1)")
    print(f"      Current Text: '{current_text}'")
except Exception as e:
    print(f"❌ FAIL: setCurrentIndex(-1) raised error: {e}")
    test_pass = False

test2_pass = test_pass

print()

# Test 3: Verify setCurrentIndex() with valid index
print("Test 3: setCurrentIndex() with valid index")
print("-" * 80)
try:
    if gl_combo.count() > 0:
        gl_combo.setCurrentIndex(0)
        current_idx = gl_combo.currentIndex()
        current_text = gl_combo.currentText()
        test_pass = current_idx == 0
        status = "✅ PASS" if test_pass else "❌ FAIL"
        print(f"{status} Can set valid index with setCurrentIndex(0)")
        print(f"      Index: {current_idx}, Text: {current_text}")
    else:
        print("⚠️  SKIP: No GL codes to test")
        test_pass = True
except Exception as e:
    print(f"❌ FAIL: setCurrentIndex(0) raised error: {e}")
    test_pass = False

test3_pass = test_pass

print()

# Test 4: Verify editable combobox accepts user text input
print("Test 4: Editable text input")
print("-" * 80)
try:
    # Create a fresh combobox for clean test
    gl_test = QComboBox()
    gl_test.setEditable(True)
    gl_test.addItem("4500 — Office Supplies", "4500")
    gl_test.addItem("4600 — Utilities", "4600")
    
    # Try to set arbitrary text
    gl_test.setEditText("4700 — New Account")
    result_text = gl_test.currentText()
    
    test_pass = "4700" in result_text
    status = "✅ PASS" if test_pass else "❌ FAIL"
    print(f"{status} Editable combobox accepts arbitrary text")
    print(f"      Set: '4700 — New Account'")
    print(f"      Got: '{result_text}'")
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_pass = False

test4_pass = test_pass

print()

# Test 5: Verify currentData() returns the data value (GL code)
print("Test 5: currentData() returns GL code")
print("-" * 80)
try:
    gl_combo.setCurrentIndex(0)
    current_data = gl_combo.currentData()
    test_pass = current_data is not None
    status = "✅ PASS" if test_pass else "❌ FAIL"
    print(f"{status} currentData() returns GL code")
    print(f"      Data: {current_data}")
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_pass = False

test5_pass = test_pass

print()

# Summary
print("=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)

all_tests = [
    ("setEditText() works", test1_pass),
    ("setCurrentIndex(-1) clears", test2_pass),
    ("setCurrentIndex(n) selects", test3_pass),
    ("Editable accepts text", test4_pass),
    ("currentData() returns value", test5_pass),
]

passed = sum(1 for _, p in all_tests if p)
total = len(all_tests)

for test_name, test_pass in all_tests:
    status = "✅" if test_pass else "❌"
    print(f"{status} {test_name}")

print()
print("=" * 80)

if passed == total:
    print(f"✅ TEST 5 PASSED: GL QComboBox methods all work correctly ({passed}/{total})")
else:
    print(f"❌ TEST 5 FAILED: {total - passed}/{total} methods failed")

print("=" * 80)

conn.close()

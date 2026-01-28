#!/usr/bin/env python
"""
TEST 4: Verify CalculatorDialog class functionality
Task: Test arithmetic evaluation
Expected: Evaluates expressions like 120+35.5-10 = 145.5
"""
import sys
sys.path.insert(0, 'L:\\limo')

from PyQt6.QtWidgets import QApplication
from desktop_app.receipt_search_match_widget import CalculatorDialog

app = QApplication([])

print("=" * 80)
print("TEST 4: CALCULATOR DIALOG FUNCTIONALITY")
print("=" * 80)
print()

# Test cases: (expression, expected_result, description)
test_cases = [
    ("120+35.5-10", 145.5, "Addition and subtraction"),
    ("100*2", 200, "Multiplication"),
    ("100/2", 50.0, "Division"),
    ("10 + 20", 30, "Expression with spaces"),
    ("(100+50)/3", 50.0, "Parentheses"),
    ("100.50 + 24.50", 125.0, "Decimal addition"),
    ("50", 50, "Single number"),
    ("1000-999.99", 0.01, "Decimal subtraction"),
]

print(f"{'Expression':<30} {'Expected':<15} {'Result':<15} {'Status'}")
print("-" * 80)

passed = 0
failed = 0

for expr, expected, description in test_cases:
    dlg = CalculatorDialog()
    dlg.input.setText(expr)
    
    result = dlg.evaluate()
    
    if result is None:
        result_str = "ERROR"
        test_pass = False
    else:
        result_str = f"{float(result):.2f}"
        # Check if close enough (floating point)
        expected_val = float(expected)
        result_val = float(result)
        test_pass = abs(result_val - expected_val) < 0.001
    
    expected_str = f"{float(expected):.2f}"
    status = "✅ PASS" if test_pass else "❌ FAIL"
    
    print(f"{expr:<30} {expected_str:<15} {result_str:<15} {status}")
    
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
print("Dialog Interface Check:")
print("-" * 80)

dlg = CalculatorDialog()
has_expression_input = hasattr(dlg, 'input')
has_evaluate_method = hasattr(dlg, 'evaluate')

print(f"✅ Has input field: {has_expression_input}")
print(f"✅ Has evaluate() method: {has_evaluate_method}")

print()
print("=" * 80)

if failed == 0 and has_expression_input and has_evaluate_method:
    print("✅ TEST 4 PASSED: CalculatorDialog evaluates expressions correctly")
else:
    print(f"❌ TEST 4 FAILED: {failed} test(s) failed or interface incomplete")

print("=" * 80)

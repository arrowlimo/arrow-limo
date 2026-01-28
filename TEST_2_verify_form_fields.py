#!/usr/bin/env python
"""
TEST 2: Verify form fields in Receipt Widget
Task: Check all form fields exist and are initialized
Expected: 13 form fields including receipt_date, vendor_name, source_reference (NOT invoice_number)
"""
import sys
sys.path.insert(0, 'L:\\limo')

try:
    import psycopg2
    import os
    from desktop_app.receipt_search_match_widget import ReceiptSearchMatchWidget
    from PyQt6.QtWidgets import QApplication
    import inspect
    
    # Get database connection
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    app = QApplication([])
    widget = ReceiptSearchMatchWidget(conn)
    
    print("=" * 80)
    print("TEST 2: RECEIPT WIDGET FORM FIELDS VERIFICATION")
    print("=" * 80)
    print()
    
    # Check for expected form fields (using actual widget attribute names)
    expected_fields = {
        'new_date': 'Date Input (DateInput)',
        'new_vendor': 'Vendor (QLineEdit)',
        'new_desc': 'Description (QLineEdit)',
        'new_amount': 'Amount (CurrencyInput)',
        'new_gl': 'GL/Category (QComboBox)',
        'payment_method': 'Payment Method (QComboBox)',
        'new_charter_input': 'Charter/Reserve Number (QLineEdit)',
        'fuel_liters': 'Fuel Liters (QDoubleSpinBox)',
        'new_banking_id': 'Banking Transaction ID (QLineEdit)',
        'new_vehicle_combo': 'Vehicle (QComboBox)',
        'new_driver_combo': 'Driver (QComboBox)',
        'gst_override_enable': 'GST Override Toggle (QPushButton)',
        'gst_override_input': 'GST Override Amount (QDoubleSpinBox)',
    }
    
    not_allowed_fields = {
        'invoice_number_input': 'invoice_number_input (should NOT exist)',
        'invoice_combo': 'invoice_combo (should NOT exist)',
    }
    
    print(f"{'Field Name':<35} {'Status':<10} {'Found'}")
    print("-" * 80)
    
    found_fields = {}
    missing_fields = []
    
    for field_name, description in expected_fields.items():
        has_field = hasattr(widget, field_name)
        found_fields[field_name] = has_field
        status = "✅ PASS" if has_field else "❌ FAIL"
        print(f"{description:<35} {status:<10} {has_field}")
        if not has_field:
            missing_fields.append(field_name)
    
    print()
    print("-" * 80)
    print("FIELDS THAT SHOULD NOT EXIST (Removed):")
    print("-" * 80)
    
    unwanted_found = []
    for field_name, description in not_allowed_fields.items():
        has_field = hasattr(widget, field_name)
        status = "❌ FAIL" if has_field else "✅ PASS"
        print(f"{description:<35} {status:<10} {has_field}")
        if has_field:
            unwanted_found.append(field_name)
    
    print()
    print("=" * 80)
    print("VERIFICATION RESULTS")
    print("=" * 80)
    
    total_expected = len(expected_fields)
    total_found = sum(1 for v in found_fields.values() if v)
    
    print(f"✅ Expected Fields Found: {total_found}/{total_expected}")
    if missing_fields:
        print(f"   Missing: {', '.join(missing_fields)}")
    
    print(f"✅ Unwanted Fields Removed: {len(unwanted_found) == 0}")
    if unwanted_found:
        print(f"   Still present: {', '.join(unwanted_found)}")
    
    # Check form layout structure
    print()
    print("-" * 80)
    print("Form Layout Structure Check:")
    print("-" * 80)
    
    has_search_panel = hasattr(widget, 'search_panel')
    has_detail_panel = hasattr(widget, 'detail_panel')
    has_table = hasattr(widget, 'results_table')
    has_form = hasattr(widget, 'form_layout')
    
    print(f"Has search_panel: {has_search_panel} ✅" if has_search_panel else f"Has search_panel: {has_search_panel} ❌")
    print(f"Has detail_panel: {has_detail_panel} ✅" if has_detail_panel else f"Has detail_panel: {has_detail_panel} ❌")
    print(f"Has results_table: {has_table} ✅" if has_table else f"Has results_table: {has_table} ❌")
    
    print()
    print("=" * 80)
    
    test_passed = (total_found == total_expected) and (len(unwanted_found) == 0) and has_search_panel and has_detail_panel and has_table
    
    if test_passed:
        print("✅ TEST 2 PASSED: All form fields are correct")
    else:
        print("❌ TEST 2 FAILED: Form field issues detected")
    
    print("=" * 80)

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

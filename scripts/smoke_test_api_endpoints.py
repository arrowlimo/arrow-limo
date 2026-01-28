#!/usr/bin/env python3
"""
Comprehensive API endpoint smoke test for desktop app integration.
Tests all endpoints that widgets use to ensure flattened receipt system works.
"""
import requests
import json
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000/api"

def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"▶️  {title}")
    print(f"{'='*70}")

def print_result(endpoint: str, status: str, details: str = ""):
    if status == "PASS":
        print(f"  ✅ {endpoint}: {status}")
    elif status == "FAIL":
        print(f"  ❌ {endpoint}: {status} - {details}")
    else:
        print(f"  ⚠️  {endpoint}: {status} - {details}")
    if details and status == "PASS":
        print(f"     {details}")

# Track results
results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "details": []
}

print_header("SMOKE TEST: All API Endpoints")
print(f"Target: {BASE_URL}")
print(f"Time: {datetime.now().isoformat()}")

# ============================================================================
# TEST 1: Receipts Endpoints
# ============================================================================
print_header("1. RECEIPTS ENDPOINTS")

try:
    # GET all receipts
    resp = requests.get(f"{BASE_URL}/receipts", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data) if isinstance(data, list) else data.get('count', 0)
        print_result("/receipts (GET)", "PASS", f"{count} receipts returned")
        results["passed"] += 1
    else:
        print_result("/receipts (GET)", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/receipts (GET)", "FAIL", str(e))
    results["failed"] += 1

try:
    # GET 2019 receipts (should have 0 with parent_receipt_id after flattening)
    resp = requests.get(
        f"{BASE_URL}/receipts",
        params={"start_date": "2019-01-01", "end_date": "2019-12-31"},
        timeout=5
    )
    if resp.status_code == 200:
        data = resp.json()
        receipts = data if isinstance(data, list) else data.get('items', [])
        parent_count = sum(1 for r in receipts if r.get('parent_receipt_id'))
        total_count = len(receipts)
        if parent_count == 0:
            print_result("/receipts (2019 filter)", "PASS", 
                        f"{total_count} receipts, {parent_count} with parent_receipt_id (✓ flattened)")
            results["passed"] += 1
        else:
            print_result("/receipts (2019 filter)", "FAIL", 
                        f"{total_count} receipts, {parent_count} still have parent_receipt_id (not flattened)")
            results["failed"] += 1
    else:
        print_result("/receipts (2019 filter)", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/receipts (2019 filter)", "FAIL", str(e))
    results["failed"] += 1

try:
    # POST new receipt (test create)
    payload = {
        "receipt_date": datetime.now().isoformat()[:10],
        "vendor_name": "SMOKE_TEST_VENDOR",
        "gross_amount": 99.99,
        "category": "other",
        "payment_method": "cash"
    }
    resp = requests.post(f"{BASE_URL}/receipts", json=payload, timeout=5)
    if resp.status_code in [200, 201]:
        new_id = resp.json().get('receipt_id')
        print_result("/receipts (POST create)", "PASS", f"Created receipt ID {new_id}")
        results["passed"] += 1
        # Store for cleanup
        results["details"].append({"type": "cleanup", "receipt_id": new_id})
    else:
        print_result("/receipts (POST create)", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/receipts (POST create)", "FAIL", str(e))
    results["failed"] += 1

# ============================================================================
# TEST 2: Accounting Endpoints
# ============================================================================
print_header("2. ACCOUNTING ENDPOINTS")

try:
    # GET accounting stats
    resp = requests.get(f"{BASE_URL}/accounting/stats", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print_result("/accounting/stats", "PASS", f"Retrieved stats (balance={data.get('total_balance', 'N/A')})")
        results["passed"] += 1
    else:
        print_result("/accounting/stats", "FAIL", f"Status {resp.status_code}")
        results["warnings"] += 1
except Exception as e:
    print_result("/accounting/stats", "FAIL", str(e))
    results["warnings"] += 1

try:
    # GET GST summary
    resp = requests.get(f"{BASE_URL}/accounting/gst-summary", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print_result("/accounting/gst-summary", "PASS", f"Retrieved GST data")
        results["passed"] += 1
    else:
        print_result("/accounting/gst-summary", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/accounting/gst-summary", "FAIL", str(e))
    results["failed"] += 1

try:
    # GET profit/loss report
    resp = requests.get(f"{BASE_URL}/accounting/reports/profit-loss", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print_result("/accounting/reports/profit-loss", "PASS", f"Retrieved P&L data")
        results["passed"] += 1
    else:
        print_result("/accounting/reports/profit-loss", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/accounting/reports/profit-loss", "FAIL", str(e))
    results["failed"] += 1

try:
    # GET cash flow report
    resp = requests.get(f"{BASE_URL}/accounting/reports/cash-flow", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print_result("/accounting/reports/cash-flow", "PASS", f"Retrieved cash flow data")
        results["passed"] += 1
    else:
        print_result("/accounting/reports/cash-flow", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/accounting/reports/cash-flow", "FAIL", str(e))
    results["failed"] += 1

try:
    # GET AR aging
    resp = requests.get(f"{BASE_URL}/accounting/reports/ar-aging", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print_result("/accounting/reports/ar-aging", "PASS", f"Retrieved AR aging data")
        results["passed"] += 1
    else:
        print_result("/accounting/reports/ar-aging", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/accounting/reports/ar-aging", "FAIL", str(e))
    results["failed"] += 1

# ============================================================================
# TEST 3: Charter Endpoints
# ============================================================================
print_header("3. CHARTER ENDPOINTS (used by widgets)")

try:
    # GET all charters
    resp = requests.get(f"{BASE_URL}/charters", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data) if isinstance(data, list) else data.get('count', 0)
        print_result("/charters (GET)", "PASS", f"{count} charters returned")
        results["passed"] += 1
    else:
        print_result("/charters (GET)", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/charters (GET)", "FAIL", str(e))
    results["failed"] += 1

# ============================================================================
# TEST 4: Vehicles Endpoints
# ============================================================================
print_header("4. VEHICLE ENDPOINTS (used by Fleet widgets)")

try:
    # GET all vehicles
    resp = requests.get(f"{BASE_URL}/vehicles", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data) if isinstance(data, list) else data.get('count', 0)
        print_result("/vehicles (GET)", "PASS", f"{count} vehicles returned")
        results["passed"] += 1
    else:
        print_result("/vehicles (GET)", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/vehicles (GET)", "FAIL", str(e))
    results["failed"] += 1

# ============================================================================
# TEST 5: Employees Endpoints
# ============================================================================
print_header("5. EMPLOYEE ENDPOINTS (used by Driver widgets)")

try:
    # GET all employees
    resp = requests.get(f"{BASE_URL}/employees", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        count = len(data) if isinstance(data, list) else data.get('count', 0)
        print_result("/employees (GET)", "PASS", f"{count} employees returned")
        results["passed"] += 1
    else:
        print_result("/employees (GET)", "FAIL", f"Status {resp.status_code}")
        results["failed"] += 1
except Exception as e:
    print_result("/employees (GET)", "FAIL", str(e))
    results["failed"] += 1

# ============================================================================
# SUMMARY
# ============================================================================
print_header("SMOKE TEST SUMMARY")
total = results["passed"] + results["failed"] + results["warnings"]
print(f"\n✅ Passed:   {results['passed']}/{total}")
print(f"❌ Failed:   {results['failed']}/{total}")
print(f"⚠️  Warnings: {results['warnings']}/{total}")

if results["failed"] == 0:
    print(f"\n🎉 ALL CRITICAL ENDPOINTS PASSED! Desktop app is ready.")
else:
    print(f"\n⚠️  {results['failed']} endpoints failed. See details above.")

print(f"\n{'='*70}")
print(f"Smoke test complete at {datetime.now().isoformat()}")
print(f"{'='*70}\n")

exit(0 if results["failed"] == 0 else 1)

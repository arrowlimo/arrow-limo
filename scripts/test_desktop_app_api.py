#!/usr/bin/env python3
"""
Quick test to verify desktop app can fetch receipts from the flattened API.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

print("=" * 70)
print("DESKTOP APP - FLATTENED RECEIPT API TEST")
print("=" * 70)

# Test 1: Get recent receipts
print("\n1. GET /api/receipts (recent receipts):")
try:
    resp = requests.get(f"{BASE_URL}/receipts?limit=5", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Receipts returned: {len(data)}")
        if data:
            r = data[0]
            print(f"   Sample: ID={r.get('receipt_id')}, Vendor={r.get('vendor')}, Amount=${r.get('amount')}")
    else:
        print(f"   ❌ Status: {resp.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Get 2019 receipts (flattened set)
print("\n2. GET /api/receipts (2019 flattened receipts):")
try:
    resp = requests.get(f"{BASE_URL}/receipts?start_date=2019-01-01&end_date=2019-12-31&limit=10", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Total 2019 receipts: {len(data)}")
        
        # Check for any with parent_receipt_id
        with_parent = [r for r in data if r.get('parent_receipt_id')]
        print(f"   Receipts with parent_receipt_id: {len(with_parent)} (should be 0)")
        
        if len(with_parent) == 0:
            print(f"   ✅ FLATTENING VERIFIED: No children found (all independent)")
    else:
        print(f"   ❌ Status: {resp.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Accounting stats
print("\n3. GET /api/accounting/stats:")
try:
    resp = requests.get(f"{BASE_URL}/accounting/stats", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Monthly Revenue: ${data.get('monthly_revenue'):,.2f}")
        print(f"   Monthly Expenses: ${data.get('monthly_expenses'):,.2f}")
        print(f"   Monthly Profit: ${data.get('monthly_profit'):,.2f}")
    else:
        print(f"   ❌ Status: {resp.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 70)
print("✅ DESKTOP APP - API INTEGRATION TEST COMPLETE")
print("=" * 70)

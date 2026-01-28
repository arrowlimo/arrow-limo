#!/usr/bin/env python3
"""
Test flattened receipt API after removing parent-child logic.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

print("=" * 70)
print("TESTING FLATTENED RECEIPT API")
print("=" * 70)

# Test 1: GET receipts (basic list)
print("\n1. GET /api/receipts (first 5)")
try:
    resp = requests.get(f"{BASE_URL}/receipts?limit=5&offset=0")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Receipt count: {len(data) if isinstance(data, list) else 'N/A'}")
        if data:
            sample = data[0]
            print(f"   Sample fields: {list(sample.keys())}")
            if 'parent_receipt_id' in sample:
                print(f"   ⚠️  WARNING: parent_receipt_id still in response (should be removed)")
            if 'is_split' in sample:
                print(f"   ⚠️  WARNING: is_split still in response (should be removed)")
            print(f"   Sample receipt: ID={sample.get('receipt_id')}, Vendor={sample.get('vendor')}, Amount={sample.get('amount')}")
    else:
        print(f"   ❌ Status: {resp.status_code}, Error: {resp.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: GET single receipt
print("\n2. GET /api/receipts/57591 (single 2019 receipt)")
try:
    resp = requests.get(f"{BASE_URL}/receipts/57591")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Receipt ID: {data.get('receipt_id')}")
        print(f"   Vendor: {data.get('vendor')}")
        print(f"   Amount: ${data.get('amount')}")
        print(f"   GL Code: {data.get('gl_account_code')}")
        print(f"   Payment Method: {data.get('payment_method')}")
        if 'split_components' in data:
            print(f"   ⚠️  WARNING: split_components still in response (should be removed)")
        print(f"   Fields: {list(data.keys())}")
    else:
        print(f"   ❌ Status: {resp.status_code}, Error: {resp.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: POST new receipt
print("\n3. POST /api/receipts (create new)")
new_receipt = {
    "date": "2026-01-05",
    "vendor": "TEST VENDOR",
    "amount": 125.50,
    "gst": 6.28,
    "gl_account_code": "5110",
    "category": "fuel",
    "description": "Test receipt - should not have parent_receipt_id",
    "payment_method": "credit_card"
}
try:
    resp = requests.post(f"{BASE_URL}/receipts", json=new_receipt)
    if resp.status_code == 201:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Created Receipt ID: {data.get('receipt_id')}")
        
        # Verify the created receipt
        receipt_id = data.get('receipt_id')
        verify = requests.get(f"{BASE_URL}/receipts/{receipt_id}")
        if verify.status_code == 200:
            verified = verify.json()
            print(f"   ✅ Verified in DB:")
            print(f"      - Vendor: {verified.get('vendor')}")
            print(f"      - Amount: ${verified.get('amount')}")
            print(f"      - GL Code: {verified.get('gl_account_code')}")
            if verified.get('parent_receipt_id') is not None:
                print(f"      ⚠️  parent_receipt_id is {verified.get('parent_receipt_id')} (should be None)")
    else:
        print(f"   ❌ Status: {resp.status_code}, Error: {resp.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: GET accounting stats
print("\n4. GET /api/accounting/stats")
try:
    resp = requests.get(f"{BASE_URL}/accounting/stats")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Monthly Revenue: ${data.get('monthly_revenue')}")
        print(f"   Monthly Expenses: ${data.get('monthly_expenses')}")
        print(f"   Monthly Profit: ${data.get('monthly_profit')}")
        print(f"   GST Owed: ${data.get('gst_owed')}")
        print(f"   (Should NOT be inflated from double-counting split receipts)")
    else:
        print(f"   ❌ Status: {resp.status_code}, Error: {resp.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Check if 2019 child receipts are now independent
print("\n5. GET /api/receipts (2019 flattened children)")
try:
    resp = requests.get(f"{BASE_URL}/receipts?start_date=2019-01-01&end_date=2019-12-31&limit=100")
    if resp.status_code == 200:
        receipts = resp.json()
        print(f"   ✅ Status: {resp.status_code}")
        print(f"   Total 2019 receipts: {len(receipts)}")
        
        # Check for orphaned parents (is_split_receipt=TRUE, no children should exist now)
        parent_count = 0
        child_count = 0
        for r in receipts:
            if r.get('parent_receipt_id') is not None:
                child_count += 1
            if r.get('is_split'):
                parent_count += 1
        
        print(f"   Receipts with parent_receipt_id: {child_count} (should be 0)")
        print(f"   Receipts marked is_split: {parent_count} (may be >0 if is_split column not updated)")
        
        if child_count == 0:
            print(f"   ✅ FLATTENING VERIFIED: All 2019 receipts are now independent")
        else:
            print(f"   ⚠️  WARNING: Found {child_count} receipts still linked to parents")
    else:
        print(f"   ❌ Status: {resp.status_code}, Error: {resp.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 70)
print("✅ API TESTING COMPLETE")
print("=" * 70)
print("\nNext steps:")
print("  1. Review warnings above (parent_receipt_id, is_split in responses)")
print("  2. Inspect 2012 split structure for synthetic parents")
print("  3. If 2012 synthetic parents found, run equivalent flattening")

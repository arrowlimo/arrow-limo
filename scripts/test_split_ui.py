#!/usr/bin/env python
"""
Test split receipt detection in the UI
Load various split receipts and verify they're detected correctly
"""

import time
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def get_test_splits():
    """Get sample split receipts to test."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cur = conn.cursor()
    
    # Get split receipts from different years
    cur.execute("""
        SELECT DISTINCT 
            r1.receipt_id, r1.receipt_date, r1.vendor_name, r1.gross_amount,
            r2.receipt_id as linked_id, r2.gross_amount as linked_amount,
            r1.description
        FROM receipts r1
        JOIN receipts r2 ON r1.vendor_name = r2.vendor_name 
                        AND r1.receipt_date = r2.receipt_date
        WHERE r1.description ILIKE '%SPLIT/%'
        AND r2.description ILIKE '%SPLIT/%'
        AND r1.receipt_id < r2.receipt_id
        ORDER BY r1.receipt_date DESC
        LIMIT 10
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return results

print("\n" + "="*100)
print("SPLIT RECEIPT DETECTION TEST")
print("="*100 + "\n")

splits = get_test_splits()

print(f"✅ Found {len(splits)} split receipt pairs to test\n")

for i, (id1, date1, vendor, amount1, id2, amount2, desc) in enumerate(splits[:5], 1):
    print(f"{i}. SPLIT GROUP:")
    print(f"   Receipt #{id1}: ${amount1:,.2f} + Receipt #{id2}: ${amount2:,.2f} = ${amount1 + amount2:,.2f}")
    print(f"   Vendor: {vendor} | Date: {date1}")
    print(f"   Description: {desc[:70]}")
    print(f"   ✅ Should detect 2 linked receipts with red banner when loading #{id1} or #{id2}\n")

print("\n" + "="*100)
print("TO TEST MANUALLY:")
print("="*100)
print("1. Look at the app Receipts tab (should still be running)")
print("2. In receipt ID filter, enter one of these IDs:")
for i, (id1, *_) in enumerate(splits[:3], 1):
    print(f"   - {id1}")
print("\n3. Press Enter or click Search")
print("4. Look for RED BANNER below search results: '📦 Split into 2 linked receipt(s) | Total: $XXX.XX'")
print("5. Verify 2 detail panels appear side-by-side with both parts of the split")
print("6. Click [Open] on the second part to verify navigation works")
print("7. Verify [View Split Details] button shows all split information")
print("\n" + "="*100 + "\n")

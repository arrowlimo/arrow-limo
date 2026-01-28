#!/usr/bin/env python3
"""
Verify split receipt 145318 and its banking links.
Check parent and 3 child receipts.
"""

import psycopg2
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("SPLIT RECEIPT VERIFICATION: Receipt 145318 & Children")
    print("=" * 100)
    
    # Get parent receipt 145318
    print("\n📋 PARENT RECEIPT (145318):")
    print("-" * 100)
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            is_split_receipt,
            parent_receipt_id,
            banking_transaction_id,
            description
        FROM receipts
        WHERE receipt_id = 145318
    """)
    
    parent = cur.fetchone()
    if parent:
        rid, rdate, vendor, amount, category, is_split, parent_id, bank_id, desc = parent
        print(f"  Receipt ID: {rid}")
        print(f"  Date: {rdate}")
        print(f"  Vendor: {vendor}")
        print(f"  Amount: ${amount:.2f}")
        print(f"  Category: {category}")
        print(f"  Is Split: {is_split}")
        print(f"  Parent ID: {parent_id}")
        print(f"  Banking Transaction ID: {bank_id}")
        print(f"  Description: {desc}")
    else:
        print("  ❌ Receipt 145318 not found!")
    
    # Get child receipts
    print("\n📋 CHILD RECEIPTS (linked to 145318):")
    print("-" * 100)
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            vehicle_id,
            is_split_receipt,
            parent_receipt_id,
            banking_transaction_id,
            description
        FROM receipts
        WHERE parent_receipt_id = 145318
        ORDER BY receipt_id
    """)
    
    children = cur.fetchall()
    if children:
        total_child_amount = 0
        for child in children:
            rid, rdate, vendor, amount, category, veh_id, is_split, parent_id, bank_id, desc = child
            total_child_amount += amount
            print(f"\n  Receipt ID: {rid}")
            print(f"    Amount: ${amount:.2f}")
            print(f"    Vehicle ID: {veh_id}")
            print(f"    Category: {category}")
            print(f"    Banking Transaction ID: {bank_id} {'⚠️  SHOULD BE NULL' if bank_id else '✓'}")
            print(f"    Description: {desc}")
        
        print(f"\n  💰 CHILD TOTAL: ${total_child_amount:.2f}")
        if parent:
            parent_amount = parent[3]
            diff = abs(parent_amount - total_child_amount)
            if diff < 0.01:
                print(f"  ✅ Matches parent: ${parent_amount:.2f}")
            else:
                print(f"  ❌ MISMATCH: Parent ${parent_amount:.2f} vs Children ${total_child_amount:.2f} (diff: ${diff:.2f})")
    else:
        print("  ❌ No child receipts found!")
    
    # Check banking transaction links
    print("\n📊 BANKING TRANSACTION MATCHING:")
    print("-" * 100)
    
    if parent and parent[7]:  # banking_transaction_id
        bank_id = parent[7]
        cur.execute("""
            SELECT 
                banking_transaction_id,
                transaction_date,
                description,
                amount,
                mapped_bank_account_id
            FROM banking_transactions
            WHERE banking_transaction_id = %s
        """, (bank_id,))
        
        bank_txn = cur.fetchone()
        if bank_txn:
            bid, bdate, bdesc, bamount, baccount = bank_txn
            print(f"  Parent linked to Banking ID: {bid}")
            print(f"    Date: {bdate}")
            print(f"    Description: {bdesc}")
            print(f"    Amount: ${bamount:.2f}")
            print(f"    Account: {baccount}")
        else:
            print(f"  ⚠️  Parent has banking_transaction_id {bank_id} but transaction not found!")
    else:
        print("  ⚠️  Parent NOT linked to banking transaction")
    
    # Check banking_receipt_matching_ledger
    print("\n📋 BANKING RECEIPT MATCHING LEDGER:")
    print("-" * 100)
    cur.execute("""
        SELECT 
            receipt_id,
            banking_transaction_id
        FROM banking_receipt_matching_ledger
        WHERE receipt_id IN (145318, 145319, 145320, 145321)
        ORDER BY receipt_id
    """)
    
    ledger = cur.fetchall()
    if ledger:
        for entry in ledger:
            rec_id, bank_id = entry
            print(f"  Receipt {rec_id} ← Banking {bank_id}")
    else:
        print("  No ledger entries found")
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY & ISSUES:")
    print("=" * 100)
    
    issues = []
    
    if not parent:
        issues.append("❌ Parent receipt 145318 does not exist!")
    else:
        if parent[7]:  # Has banking link
            print("✓ Parent is linked to banking transaction")
        else:
            issues.append("⚠️  Parent NOT linked to banking")
    
    if not children:
        issues.append("❌ No child receipts found (should have 3)")
    else:
        print(f"✓ Found {len(children)} child receipts")
        
        # Check if children have banking links
        child_bank_links = sum(1 for c in children if c[8] is not None)
        if child_bank_links > 0:
            issues.append(f"❌ {child_bank_links} child receipt(s) incorrectly linked to banking (should be 0)")
        else:
            print("✓ No child receipts linked to banking (correct)")
    
    if issues:
        print("\n🔴 ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ NO ISSUES - Split receipt structure is correct!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

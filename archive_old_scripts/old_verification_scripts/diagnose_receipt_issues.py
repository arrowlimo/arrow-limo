"""Diagnose receipt linking and Centex banking match issues"""
import sys
import os

# Set environment to avoid authentication issues
os.environ.setdefault('DB_TARGET', 'local')

sys.path.insert(0, 'l:\\limo\\modern_backend')

try:
    from app.db import get_connection
    
    conn = get_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("ISSUE #1: RECEIPTS TABLE SCHEMA CHECK")
    print("=" * 100)
    
    # Check if charter_id, employee_id (driver), and vehicle_id columns exist
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'receipts'
        AND column_name IN ('charter_id', 'employee_id', 'vehicle_id', 'reserve_number')
        ORDER BY column_name
    """)
    
    cols = cur.fetchall()
    print("\nLinking columns in receipts table:")
    for col in cols:
        print(f"  ✅ {col[0]:20} ({col[1]})")
    
    required = ['charter_id', 'employee_id', 'vehicle_id']
    found = [col[0] for col in cols]
    missing = [col for col in required if col not in found]
    
    if missing:
        print(f"\n❌ MISSING COLUMNS: {', '.join(missing)}")
    else:
        print("\n✅ All linking columns exist!")
    
    print("\n" + "=" * 100)
    print("ISSUE #2: CENTEX BANKING MATCH FOR 01/04/2012 - $225.01")
    print("=" * 100)
    
    # Search for Centex banking transactions around January 4, 2012
    print("\nSearching banking_transactions for Centex near 2012-01-04 with amount ~$225.01...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               debit_amount, credit_amount, account_number, receipt_id
        FROM banking_transactions
        WHERE LOWER(description) LIKE '%centex%'
        AND transaction_date BETWEEN '2012-01-01' AND '2012-01-10'
        ORDER BY transaction_date
    """)
    
    transactions = cur.fetchall()
    print(f"\nFound {len(transactions)} Centex transaction(s) in early January 2012:")
    
    for txn in transactions:
        tid, tdate, desc, debit, credit, acct, receipt_id = txn
        amount = debit if debit else credit
        match_225 = abs(float(amount or 0) - 225.01) < 0.02 if amount else False
        marker = "🎯" if match_225 else "  "
        receipt_status = f"Linked to Receipt #{receipt_id}" if receipt_id else "NOT LINKED"
        
        print(f"\n{marker} Transaction ID: {tid}")
        print(f"   Date: {tdate}")
        print(f"   Description: {desc}")
        print(f"   Amount: ${amount} ({'debit' if debit else 'credit'})")
        print(f"   Account: {acct}")
        print(f"   Status: {receipt_status}")
    
    if not transactions:
        print("  ❌ NO Centex transactions found in early January 2012!")
        print("\n  Expanding search to all of January 2012...")
        cur.execute("""
            SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
            FROM banking_transactions
            WHERE LOWER(description) LIKE '%centex%'
            AND transaction_date BETWEEN '2012-01-01' AND '2012-01-31'
        """)
        jan_result = cur.fetchone()
        print(f"  Found {jan_result[0]} Centex transactions in all of January")
        if jan_result[0] > 0:
            print(f"  Date range: {jan_result[1]} to {jan_result[2]}")
    
    # Check for receipts with this criteria
    print("\n\nSearching receipts for Centex near 2012-01-04 with amount ~$225.01...")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount,
               vehicle_id, charter_id, employee_id, banking_transaction_id
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%centex%'
        AND receipt_date BETWEEN '2012-01-01' AND '2012-01-10'
        ORDER BY receipt_date
    """)
    
    receipts = cur.fetchall()
    print(f"\nFound {len(receipts)} Centex receipt(s) in early January 2012:")
    
    for rec in receipts:
        rid, rdate, vendor, amount, vid, cid, eid, bid = rec
        match_225 = abs(float(amount or 0) - 225.01) < 0.02 if amount else False
        marker = "🎯" if match_225 else "  "
        
        print(f"\n{marker} Receipt ID: {rid}")
        print(f"   Date: {rdate}")
        print(f"   Vendor: {vendor}")
        print(f"   Amount: ${amount}")
        print(f"   Vehicle ID: {vid or 'NOT SET'}")
        print(f"   Charter ID: {cid or 'NOT SET'}")  
        print(f"   Employee ID (Driver): {eid or 'NOT SET'}")
        print(f"   Banking Transaction ID: {bid or 'NOT LINKED'}")
    
    if not receipts:
        print("  ❌ NO Centex receipts found in early January 2012!")
    
    # Summary
    print("\n" + "=" * 100)
    print("DIAGNOSIS SUMMARY")
    print("=" * 100)
    
    print("\n1. SCHEMA ISSUES:")
    if missing:
        print(f"   ❌ Missing columns in receipts table: {', '.join(missing)}")
    else:
        print("   ✅ All required columns exist in database")
    
    print("\n2. API ISSUES:")
    print("   ❌ Frontend ReceiptForm.vue does NOT have driver selection field")
    print("   ❌ Frontend only captures charter_number (text), not charter_id (FK)")
    print("   ❌ Backend receipts_simple.py does NOT insert charter_id or employee_id")
    print("   ⚠️  Backend only inserts: vehicle_id")
    
    print("\n3. CENTEX BANKING MATCH:")
    if not transactions:
        print("   ❌ No banking transactions found for Centex on/near 01/04/2012")
        print("   💡 Check if data was imported for that date range")
    else:
        has_225 = any(abs(float(t[3] or t[4] or 0) - 225.01) < 0.02 for t in transactions)
        if has_225:
            print("   ✅ Found matching transaction(s) for $225.01")
            unlinked = [t for t in transactions if not t[6] and abs(float(t[3] or t[4] or 0) - 225.01) < 0.02]
            if unlinked:
                print(f"   ⚠️  {len(unlinked)} matching transaction(s) NOT linked to receipt")
        else:
            print("   ⚠️  Found Centex transactions but none matching $225.01")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

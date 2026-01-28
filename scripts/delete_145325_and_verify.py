#!/usr/bin/env python3
"""
Delete receipt 145325 (FAS GAS duplicate) and verify final state.
"""

import psycopg2

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
    
    print("=" * 120)
    print("DELETE RECEIPT 145325 (FAS GAS DUPLICATE)")
    print("=" * 120)
    
    # Show what we're deleting
    print("\n🗑️  RECEIPT TO DELETE:")
    print("-" * 120)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description
        FROM receipts
        WHERE receipt_id = 145325
    """)
    
    rec = cur.fetchone()
    if rec:
        rid, rdate, vendor, amt, desc = rec
        print(f"  Receipt {rid} | {rdate} | {vendor} | ${amt:.2f}")
        print(f"  Description: {desc}")
    else:
        print("  Receipt not found!")
        return False
    
    # Delete it
    print("\n" + "=" * 120)
    print("DELETING...")
    print("=" * 120)
    
    try:
        cur.execute("DELETE FROM receipts WHERE receipt_id = 145325")
        deleted = cur.rowcount
        conn.commit()
        print(f"\n✓ Deleted {deleted} receipt")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        return False
    
    # Final verification
    print("\n" + "=" * 120)
    print("FINAL VERIFICATION: Correct 09/15/2012 Fuel Receipts for Banking 69336")
    print("=" * 120)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            banking_transaction_id
        FROM receipts
        WHERE receipt_id IN (145322, 145323, 140662)
        ORDER BY receipt_id
    """)
    
    total = 0
    for rec in cur.fetchall():
        rid, rdate, vendor, amt, bank_id = rec
        total += amt
        print(f"  Receipt {rid} | {rdate} | {vendor:20} | ${amt:>10.2f} | Banking {bank_id}")
    
    print(f"\n  💰 TOTAL: ${total:.2f}")
    
    # Verify against banking
    cur.execute("""
        SELECT 
            transaction_id,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE transaction_id = 69336
    """)
    
    bank = cur.fetchone()
    if bank:
        bid, bdesc, damt, camt = bank
        bank_amt = damt if damt and damt > 0 else camt
        print(f"\n  Banking {bid} ({bdesc}): ${bank_amt:.2f}")
        
        if abs(total - bank_amt) < 0.01:
            print(f"\n✅ PERFECT MATCH - BALANCED!")
            return True
        else:
            print(f"\n❌ MISMATCH - Diff: ${abs(total - bank_amt):.2f}")
            return False
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    success = main()
    print("\n" + "=" * 120)
    if success:
        print("🎉 ALL FIXED AND VERIFIED!")
    else:
        print("⚠️  ISSUES REMAIN")
    print("=" * 120)
    exit(0 if success else 1)

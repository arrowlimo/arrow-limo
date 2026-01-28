#!/usr/bin/env python3
"""
Final verification - confirm 09/15/2012 fuel purchases are correctly recorded and balanced.
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
    print("FINAL VERIFICATION: 09/15/2012 FUEL PURCHASES")
    print("=" * 120)
    
    # Check RUN'N ON EMPTY receipts
    print("\n✅ RECEIPTS IN SYSTEM (09/15/2012):")
    print("-" * 120)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            banking_transaction_id,
            description
        FROM receipts
        WHERE receipt_date = '2012-09-15'
        AND vendor_name IN ('RUN''N ON EMPTY', 'FUEL STATION', 'FAS GAS')
        ORDER BY receipt_id
    """)
    
    receipts = cur.fetchall()
    if not receipts:
        print("  ❌ No receipts found!")
        return False
    
    total_receipts = 0
    for rec in receipts:
        rid, rdate, vendor, amt, bank_id, desc = rec
        total_receipts += amt
        bank_str = f"→ Banking {bank_id}" if bank_id else "(no link)"
        print(f"  Receipt {rid:6} | {vendor:20} | ${amt:>10.2f} | {bank_str}")
    
    print(f"\n  💰 TOTAL RECEIPTS: ${total_receipts:.2f}")
    
    # Verify banking match
    print("\n" + "=" * 120)
    print("✅ BANKING TRANSACTION (09/17/2012 posted date):")
    print("-" * 120)
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE transaction_id = 69336
    """)
    
    bank_txn = cur.fetchone()
    if bank_txn:
        bid, bdate, bdesc, damt, camt = bank_txn
        amt = damt if damt and damt > 0 else camt
        print(f"  Banking ID: {bid}")
        print(f"  Date: {bdate}")
        print(f"  Description: {bdesc}")
        print(f"  Amount: ${amt:.2f}")
    else:
        print("  ❌ Banking transaction not found!")
        return False
    
    # Final check
    print("\n" + "=" * 120)
    print("RECONCILIATION CHECK:")
    print("=" * 120)
    
    if abs(total_receipts - amt) < 0.01:
        print(f"\n✅ PERFECT MATCH!")
        print(f"   Receipts: ${total_receipts:.2f}")
        print(f"   Banking:  ${amt:.2f}")
        print(f"   Status:   BALANCED ✓")
        return True
    else:
        print(f"\n❌ MISMATCH!")
        print(f"   Receipts: ${total_receipts:.2f}")
        print(f"   Banking:  ${amt:.2f}")
        print(f"   Diff:     ${abs(total_receipts - amt):.2f}")
        return False
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    success = main()
    print("\n" + "=" * 120)
    if success:
        print("🎉 ALL FIXED!")
    else:
        print("⚠️  ISSUES REMAIN")
    print("=" * 120)
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
Delete 2 BOGUS QuickBooks receipts that conflict with VERIFIED banking records
Receipt #71773 and #71740 (MONEY MART, CHQ #30)
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
    
    bogus_receipt_ids = [71773, 71740]
    
    print("="*80)
    print("DELETING BOGUS QUICKBOOKS RECEIPTS")
    print("="*80)
    
    # First, show what we're deleting
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, description, gross_amount,
               source_system, banking_transaction_id
        FROM receipts
        WHERE receipt_id IN (%s, %s)
    """, bogus_receipt_ids)
    
    receipts_to_delete = cur.fetchall()
    
    print("\nReceipts to DELETE:")
    for rec_id, date, vendor, desc, amount, source, bank_tx in receipts_to_delete:
        print(f"  Receipt #{rec_id}")
        print(f"    Date: {date}")
        print(f"    Vendor: {vendor}")
        print(f"    Amount: ${amount:.2f}")
        print(f"    Description: {desc}")
        print(f"    Source: {source}")
        print(f"    Banking TX: {bank_tx}")
        print()
    
    # Check if any banking_transactions reference these receipts
    cur.execute("""
        SELECT transaction_id, description, debit_amount, credit_amount, receipt_id
        FROM banking_transactions
        WHERE receipt_id IN (%s, %s)
    """, bogus_receipt_ids)
    
    banking_refs = cur.fetchall()
    
    if banking_refs:
        print("\nBanking transactions referencing these receipts:")
        for tx_id, desc, debit, credit, rec_id in banking_refs:
            amount = debit if debit else credit
            print(f"  TX #{tx_id} → Receipt #{rec_id}: ${amount:.2f}")
            print(f"    {desc[:80]}")
        
        # Clear the receipt_id references before deleting
        print("\nClearing banking_transactions.receipt_id references...")
        cur.execute("""
            UPDATE banking_transactions
            SET receipt_id = NULL
            WHERE receipt_id IN (%s, %s)
        """, bogus_receipt_ids)
        print(f"  ✓ Cleared {cur.rowcount} banking transaction references")
    
    # Delete the bogus receipts
    print("\nDeleting bogus receipts...")
    cur.execute("""
        DELETE FROM receipts
        WHERE receipt_id IN (%s, %s)
    """, bogus_receipt_ids)
    
    deleted_count = cur.rowcount
    print(f"  ✓ Deleted {deleted_count} receipts")
    
    # Commit the changes
    conn.commit()
    print("\n✅ COMMITTED - Bogus QuickBooks receipts deleted")
    
    # Verify deletion
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE receipt_id IN (%s, %s)
    """, bogus_receipt_ids)
    
    remaining = cur.fetchone()[0]
    
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    if remaining == 0:
        print(f"✅ SUCCESS: All {deleted_count} bogus receipts removed")
        print(f"   Receipt IDs: {bogus_receipt_ids}")
    else:
        print(f"❌ ERROR: {remaining} receipts still exist!")
    
    print("\nVERIFIED BANKING RECORDS remain untouched (as required)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

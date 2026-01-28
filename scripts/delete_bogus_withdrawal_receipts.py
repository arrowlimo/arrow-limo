#!/usr/bin/env python3
"""
Delete bogus receipts (withdrawals/deposits not in banking).

These are likely duplicate entries from old data imports.
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
    
    print("=" * 80)
    print("DELETING BOGUS RECEIPTS (NOT IN BANKING)")
    print("=" * 80)
    
    # Get all large withdrawal/deposit receipts NOT in banking
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.category,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM banking_transactions bt
                    WHERE bt.transaction_date = r.receipt_date
                      AND ABS(bt.debit_amount - r.gross_amount) < 0.01
                ) THEN 'HAS_MATCH'
                ELSE 'NO_MATCH'
            END as has_banking_match
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        WHERE brml.receipt_id IS NULL
          AND (r.vendor_name LIKE '%WITHDRAWAL%'
           OR r.vendor_name LIKE '%CASH WITHDRAWAL%'
           OR r.vendor_name LIKE '%ATM DEPOSIT%'
           OR r.vendor_name LIKE '%BRANCH WITHDRAWAL%')
          AND r.gross_amount > 1000
        ORDER BY r.gross_amount DESC
    """)
    
    bogus_receipts = cur.fetchall()
    
    to_delete = []
    to_keep = []
    
    for receipt_id, date, vendor, amount, category, has_match in bogus_receipts:
        if has_match == 'NO_MATCH':
            to_delete.append((receipt_id, date, vendor, amount))
        else:
            to_keep.append((receipt_id, date, vendor, amount))
    
    print(f"\nFound {len(bogus_receipts)} large withdrawal/deposit receipts NOT linked to banking:")
    print(f"  {len(to_delete)} have NO matching banking transaction (BOGUS - will delete)")
    print(f"  {len(to_keep)} have matching banking (need manual matching)")
    
    if to_delete:
        print(f"\n{len(to_delete)} BOGUS receipts to delete (NO banking match):")
        total_bogus = sum(amt for _, _, _, amt in to_delete)
        for receipt_id, date, vendor, amount in to_delete[:20]:  # Show first 20
            print(f"  {receipt_id} | {date} | {vendor[:40]:40} | ${amount:,.2f}")
        if len(to_delete) > 20:
            print(f"  ... and {len(to_delete) - 20} more")
        print(f"\nTotal bogus amount: ${total_bogus:,.2f}")
        
        # Delete them
        receipt_ids_to_delete = [r[0] for r in to_delete]
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id = ANY(%s)
        """, (receipt_ids_to_delete,))
        
        print(f"\n✅ Deleted {len(to_delete)} bogus receipts (${total_bogus:,.2f})")
    
    if to_keep:
        print(f"\n{len(to_keep)} receipts need manual matching (have banking match but not linked):")
        for receipt_id, date, vendor, amount in to_keep[:10]:  # Show first 10
            print(f"  {receipt_id} | {date} | {vendor[:40]:40} | ${amount:,.2f}")
        print("\nThese are from 2012-2014 period - already matched but receipt not deleted properly")
    
    conn.commit()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

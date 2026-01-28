"""
Sync Receipt Vendor Names from Verified Banking Descriptions
=============================================================

Updates receipt vendor_name to match the banking transaction description
when a receipt is linked to a banking transaction.

This ensures vendor names are standardized and accurate based on 
verified bank statement data.

Author: AI Agent
Date: December 19, 2025
"""

import psycopg2
import os
from datetime import datetime

# Database configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    print("="*70)
    print("SYNC RECEIPT VENDOR NAMES FROM BANKING")
    print("="*70)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Find mismatched vendor names
    print("\n1. Finding receipts with mismatched vendor names...")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, b.description, r.gross_amount, r.receipt_date
        FROM receipts r 
        JOIN banking_transactions b ON r.banking_transaction_id = b.transaction_id 
        WHERE r.vendor_name != b.description 
        AND r.banking_transaction_id IS NOT NULL
        ORDER BY r.receipt_date DESC
    """)
    
    mismatches = cur.fetchall()
    print(f"   Found {len(mismatches):,} receipts with mismatched vendor names")
    
    if len(mismatches) == 0:
        print("\n✅ All receipt vendor names already match banking descriptions!")
        conn.close()
        return
    
    # Show sample
    print(f"\n2. Sample mismatches (first 10):")
    for i, (receipt_id, receipt_vendor, banking_vendor, amount, date) in enumerate(mismatches[:10]):
        print(f"   {receipt_id:6} {date}: '{receipt_vendor[:25]:25}' → '{banking_vendor[:25]:25}' ${amount:>10,.2f}")
    
    if len(mismatches) > 10:
        print(f"   ... and {len(mismatches) - 10:,} more")
    
    # Confirm
    response = input(f"\nUpdate {len(mismatches):,} receipt vendor names? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Cancelled")
        conn.close()
        return
    
    # Update vendor names
    print(f"\n3. Updating vendor names...")
    cur.execute("""
        UPDATE receipts r
        SET vendor_name = b.description
        FROM banking_transactions b
        WHERE r.banking_transaction_id = b.transaction_id
        AND r.vendor_name != b.description
    """)
    
    updated_count = cur.rowcount
    conn.commit()
    
    print(f"   ✅ Updated {updated_count:,} receipt vendor names")
    
    # Verify
    print(f"\n4. Verifying updates...")
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts r 
        JOIN banking_transactions b ON r.banking_transaction_id = b.transaction_id 
        WHERE r.vendor_name != b.description
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print(f"   ✅ All receipt vendor names now match banking descriptions!")
    else:
        print(f"   ⚠️ Still {remaining:,} mismatches (may need manual review)")
    
    # Show updated vendor distribution
    print(f"\n5. Top vendors after update:")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY vendor_name
        ORDER BY count DESC
        LIMIT 15
    """)
    
    for vendor, count, total in cur.fetchall():
        print(f"   {vendor[:40]:40} {count:>6,} receipts ${total:>12,.2f}")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"✅ Updated {updated_count:,} receipt vendor names from banking descriptions")
    print(f"✅ Vendor names now standardized and accurate")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()

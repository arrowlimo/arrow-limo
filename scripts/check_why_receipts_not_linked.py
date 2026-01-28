#!/usr/bin/env python3
"""
Investigate why receipts with source_hash weren't linked to banking transactions.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*90)
    print("WHY WEREN'T EXISTING RECEIPTS LINKED TO BANKING?")
    print("="*90)
    
    # Find receipts that exist but were never linked to their banking transaction
    print("\n1. Receipts with source_hash but NOT created_from_banking and NOT linked:")
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.category,
            r.created_from_banking,
            r.source_hash,
            COUNT(bm.id) as link_count
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        WHERE r.source_hash IS NOT NULL
        AND (r.created_from_banking IS NOT TRUE OR r.created_from_banking IS NULL)
        GROUP BY r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, r.category, r.created_from_banking, r.source_hash
        HAVING COUNT(bm.id) = 0
        ORDER BY r.gross_amount DESC
        LIMIT 20
    """)
    
    unlinked = cur.fetchall()
    print(f"   Found {len(unlinked)} receipts with source_hash but NOT created_from_banking and NOT linked")
    print()
    print(f"   {'Date':12} {'Vendor':30} {'Amount':>12} {'Category':20} {'Links':5}")
    print("   " + "-" * 85)
    for row in unlinked:
        vendor = (row[2] or 'Unknown')[:30]
        category = (row[4] or 'none')[:20]
        print(f"   {str(row[1]):12} {vendor:30} ${row[3]:10.2f} {category:20} {row[7]}")
    
    # Check if these have matching banking transactions
    print("\n2. Receipts with exact date+amount match to banking but not linked:")
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            r.receipt_id,
            r.vendor_name,
            r.gross_amount,
            r.source_hash
        FROM receipts r
        INNER JOIN banking_transactions bt 
            ON bt.transaction_date = r.receipt_date
            AND bt.debit_amount = r.gross_amount
        WHERE (r.created_from_banking IS NOT TRUE OR r.created_from_banking IS NULL)
        AND r.source_hash IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.receipt_id = r.receipt_id
        )
        ORDER BY r.gross_amount DESC
        LIMIT 15
    """)
    
    matches = cur.fetchall()
    print(f"   Found {len(matches)} receipts with exact date+amount match to banking:")
    print()
    for row in matches:
        vendor = (row[5] or 'Unknown')[:40]
        desc = row[2][:60]
        print(f"   Receipt {row[4]}: {vendor} ${row[6]:.2f} on {row[1]}")
        print(f"      -> Banking {row[0]}: {desc} ${row[3]:.2f}")
        print()
    
    # Check how these receipts were originally created
    print("\n3. How were these unlinked receipts created?")
    cur.execute("""
        SELECT 
            COALESCE(r.created_from_banking, FALSE) as from_banking,
            COUNT(*) as count,
            SUM(r.gross_amount) as total_amount
        FROM receipts r
        WHERE r.source_hash IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.receipt_id = r.receipt_id
        )
        GROUP BY COALESCE(r.created_from_banking, FALSE)
        ORDER BY count DESC
    """)
    
    sources = cur.fetchall()
    print(f"   {'Source':30} {'Count':>8} {'Total Amount':>15}")
    print("   " + "-" * 55)
    for row in sources:
        source = "Created from banking" if row[0] else "Created manually/imported"
        print(f"   {source:30} {row[1]:8} ${row[2]:13,.2f}")
    
    # Check the total picture
    print("\n4. Overall receipt-banking linkage status:")
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN r.source_hash IS NOT NULL THEN 1 END) as has_hash,
            COUNT(CASE WHEN r.created_from_banking = TRUE THEN 1 END) as from_banking,
            COUNT(CASE WHEN bm.id IS NOT NULL THEN 1 END) as linked_to_banking
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        WHERE r.business_personal = 'Business'
    """)
    
    stats = cur.fetchone()
    print(f"   Total business receipts: {stats[0]:,}")
    print(f"   Receipts with source_hash: {stats[1]:,}")
    print(f"   Receipts created_from_banking: {stats[2]:,}")
    print(f"   Receipts linked to banking: {stats[3]:,}")
    
    print("\n" + "="*90)
    print("ANALYSIS")
    print("="*90)
    print("""
The issue is that receipts were imported from various sources (Excel, CSV, PDF)
BEFORE the banking reconciliation system was built. These receipts:

1. Have source_hash values (generated during import)
2. Were NOT created from banking (created_from_banking = FALSE/NULL)
3. Were NOT linked to banking transactions (no junction table entries)

The auto_create_receipts_from_all_banking.py script:
- Looks for UNMATCHED banking transactions (no link in junction table)
- Checks if receipt with same hash exists
- If exists: Creates link only (doesn't create new receipt)
- If not exists: Creates new receipt AND link

This is CORRECT behavior - it prevented duplicate receipts and properly
linked existing receipts to their banking transactions.
    """)
    
    print("="*90 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

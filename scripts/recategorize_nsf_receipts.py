#!/usr/bin/env python3
"""
Recategorize NSF receipts to properly reflect bounced company checks.

Target: Oct 29, 2012 CHQ 36 ($1,900.50) and CHQ 30 ($2,525.25)
These were company checks that bounced, then successfully reissued Nov 14.
"""

import psycopg2
import os
import argparse
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Recategorize NSF receipts')
    parser.add_argument('--write', action='store_true', help='Apply changes (default: dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find the specific Oct 29, 2012 NSF receipts
    cur.execute("""
        SELECT id, receipt_date, vendor_name, gross_amount, 
               category, description, source_reference
        FROM receipts
        WHERE receipt_date = '2012-10-29'
          AND description LIKE '%RETURNED NSF CHEQUE%'
        ORDER BY gross_amount
    """)
    
    oct_29_receipts = cur.fetchall()
    
    print(f"\nOct 29, 2012 NSF Receipts Found: {len(oct_29_receipts)}")
    print("=" * 120)
    
    for row in oct_29_receipts:
        rid, date, vendor, amount, cat, desc, source_ref = row
        print(f"ID: {rid:6} | Date: {date} | Amount: ${amount:8.2f}")
        print(f"         Current Category: {cat}")
        print(f"         Description: {desc}")
        print(f"         Source: {source_ref}")
        print()
    
    if not oct_29_receipts:
        print("No receipts found matching criteria!")
        cur.close()
        conn.close()
        return
    
    # Update category and description
    new_category = "failed_payment"
    new_desc_prefix = "Company check bounced - "
    
    if args.write:
        print("\nAPPLYING UPDATES...")
        for row in oct_29_receipts:
            rid, date, vendor, amount, cat, old_desc, source_ref = row
            
            # Determine which check this was
            if abs(amount - Decimal('1900.50')) < Decimal('0.01'):
                check_info = "CHQ 36 to Heffner Auto Finance"
            elif abs(amount - Decimal('2525.25')) < Decimal('0.01'):
                check_info = "CHQ 30 to Heffner Auto Finance"
            else:
                check_info = "payment to Heffner Auto Finance"
            
            new_desc = f"{new_desc_prefix}{check_info}. {old_desc}"
            
            cur.execute("""
                UPDATE receipts
                SET category = %s,
                    description = %s,
                    vendor_name = 'Heffner Auto Finance'
                WHERE id = %s
            """, (new_category, new_desc, rid))
            
            print(f"✓ Updated receipt {rid}: {vendor} -> Heffner Auto Finance")
            print(f"  Category: {cat} -> {new_category}")
            print(f"  Description: {new_desc[:80]}...")
            print()
        
        conn.commit()
        print(f"\n✓ Updated {len(oct_29_receipts)} receipts")
        
        # Verify updates
        print("\nVerifying updates:")
        for row in oct_29_receipts:
            rid = row[0]
            cur.execute("""
                SELECT category, vendor_name, description
                FROM receipts 
                WHERE id = %s
            """, (rid,))
            cat, vendor, desc = cur.fetchone()
            print(f"  {rid}: {vendor:30} | {cat:20} | {desc[:60]}")
    else:
        print("\nDRY-RUN MODE - would update:")
        for row in oct_29_receipts:
            rid, date, vendor, amount, cat, old_desc, source_ref = row
            
            if abs(amount - Decimal('1900.50')) < Decimal('0.01'):
                check_info = "CHQ 36 to Heffner Auto Finance"
            elif abs(amount - Decimal('2525.25')) < Decimal('0.01'):
                check_info = "CHQ 30 to Heffner Auto Finance"
            else:
                check_info = "payment to Heffner Auto Finance"
            
            new_desc = f"{new_desc_prefix}{check_info}. {old_desc}"
            
            print(f"  Receipt {rid}:")
            print(f"    Vendor: {vendor} -> Heffner Auto Finance")
            print(f"    Category: {cat} -> {new_category}")
            print(f"    Description: {new_desc[:80]}...")
            print()
        
        print("\nRun with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

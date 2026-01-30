#!/usr/bin/env python3
"""
STEP 6: Remove duplicate receipts from Scotia auto-creation.
The issue: Scotia and original CIBC receipts have same date+vendor+amount.
Keep the CIBC version (created_from_banking=false, manually verified).
Remove Scotia version (created_from_banking=true, auto-generated).
"""

import os
import psycopg2

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "almsdata"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "***REDACTED***"),
}

def remove_scotia_auto_duplicates(dry_run=True):
    """Remove Scotia auto-created receipts that duplicate CIBC versions."""
    print("\n" + "="*80)
    print("STEP 6: REMOVE SCOTIA AUTO-DUPLICATES (Keep CIBC, Remove Scotia)")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Find receipts where same date+vendor+amount exists in both Scotia and CIBC
        cur.execute("""
            SELECT DISTINCT 
                s.receipt_id as scotia_id,
                c.receipt_id as cibc_id,
                s.receipt_date,
                s.vendor_name,
                s.gross_amount
            FROM receipts s
            JOIN receipts c ON s.receipt_date = c.receipt_date
                AND s.vendor_name = c.vendor_name
                AND s.gross_amount = c.gross_amount
            WHERE EXTRACT(YEAR FROM s.receipt_date) = 2012
              AND s.mapped_bank_account_id = 2  -- Scotia
              AND s.created_from_banking = true  -- Auto-created
              AND c.mapped_bank_account_id = 1  -- CIBC
              AND (c.created_from_banking = false OR c.created_from_banking IS NULL)  -- Manual
            ORDER BY s.receipt_date, s.vendor_name
        """)
        
        duplicates = cur.fetchall()
        print(f"Found {len(duplicates)} Scotia auto-receipts duplicating CIBC versions\n")
        
        if duplicates:
            scotia_to_delete = [row[0] for row in duplicates]
            
            print("Sample duplicates (keeping CIBC, removing Scotia):")
            for scotia_id, cibc_id, date, vendor, amount in duplicates[:20]:
                print(f"  {date} {vendor[:25]:25s} ${amount:>10.2f}")
                print(f"    Remove Scotia ID {scotia_id}, Keep CIBC ID {cibc_id}")
            
            if not dry_run:
                # Delete ledger entries for Scotia receipts
                cur.execute("""
                    DELETE FROM banking_receipt_matching_ledger
                    WHERE receipt_id = ANY(%s)
                """, (scotia_to_delete,))
                ledger_del = cur.rowcount
                
                # Delete Scotia receipts
                cur.execute("""
                    DELETE FROM receipts
                    WHERE receipt_id = ANY(%s)
                """, (scotia_to_delete,))
                receipt_del = cur.rowcount
                
                conn.commit()
                print(f"\n[OK] Removed {receipt_del} Scotia auto-duplicates, {ledger_del} ledger entries")
            else:
                print(f"\n[DRY-RUN] Would remove {len(duplicates)} Scotia auto-duplicates")
        
        return len(duplicates)
    
    finally:
        cur.close()
        conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Remove Scotia auto-duplicates')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--write', action='store_true', help='Apply changes to DB')
    args = parser.parse_args()
    
    if not args.write:
        args.dry_run = True
    
    count = remove_scotia_auto_duplicates(dry_run=args.dry_run)
    
    print("\n" + "="*80)
    print(f"RESULT: {count} Scotia auto-duplicates removed")
    print("="*80)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
STEP 4: Dedup receipts - remove QuickBooks import artifacts.
Patterns to remove:
- "Cheque #dd" prefix (QuickBooks artifact)
- " X" suffix (QuickBooks artifact)
- Exact duplicates by date+amount+vendor (after stripping artifacts)
"""

import os
import psycopg2

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "almsdata"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "***REMOVED***"),
}

def dedup_receipts(dry_run=False):
    """Remove QB artifact receipts and exact duplicates."""
    print("\n" + "="*80)
    print("STEP 4: DEDUP RECEIPTS (Remove QB Artifacts)")
    print("="*80)
    print(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")
    
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    
    try:
        # Find receipts with QB artifacts
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, description, gross_amount
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND (description LIKE 'Cheque #dd%' OR description LIKE '% X')
            ORDER BY receipt_date, vendor_name
        """)
        
        artifact_rows = cur.fetchall()
        print(f"Found {len(artifact_rows)} receipts with QB artifacts")
        
        if artifact_rows:
            print("\nSample artifacts to remove:")
            for receipt_id, date, vendor, desc, amount in artifact_rows[:10]:
                print(f"  ID {receipt_id}: {date} {vendor[:30]:30s} {amount:>10.2f}")
                if desc:
                    print(f"    Desc: {desc[:60]}")
        
        if not dry_run and artifact_rows:
            artifact_ids = [row[0] for row in artifact_rows]
            
            # Delete from ledger first (FK constraint)
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE receipt_id = ANY(%s)
            """, (artifact_ids,))
            ledger_del = cur.rowcount
            
            # Delete receipts
            cur.execute("""
                DELETE FROM receipts
                WHERE receipt_id = ANY(%s)
            """, (artifact_ids,))
            receipt_del = cur.rowcount
            
            conn.commit()
            print(f"\n[OK] Removed {receipt_del} artifact receipts, {ledger_del} ledger entries")
        else:
            print(f"\n[DRY-RUN] Would remove {len(artifact_rows)} artifact receipts")
        
        # Now find exact duplicates by date+vendor+amount (CIBC only, since Scotia was rebuilt fresh)
        cur.execute("""
            SELECT receipt_date, vendor_name, gross_amount, COUNT(*) as cnt,
                   ARRAY_AGG(receipt_id ORDER BY receipt_id) as ids
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
              AND category NOT IN ('inter_account_transfer')
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """)
        
        dup_groups = cur.fetchall()
        print(f"\nFound {len(dup_groups)} duplicate groups (date+vendor+amount)")
        
        total_dups = sum(row[3] for row in dup_groups)
        print(f"Total duplicate rows: {total_dups}")
        
        if dup_groups:
            print("\nLargest duplicate groups (keeping first, removing rest):")
            for date, vendor, amount, cnt, ids in dup_groups[:15]:
                print(f"  {date} | {vendor[:30]:30s} | ${amount:>10.2f} | {cnt} rows")
                print(f"    Keep ID {ids[0]}, remove {cnt-1}: {ids[1:]}")
        
        if not dry_run and dup_groups:
            ids_to_delete = []
            for date, vendor, amount, cnt, ids in dup_groups:
                # Keep first ID, delete rest
                ids_to_delete.extend(ids[1:])
            
            if ids_to_delete:
                # Delete ledger entries
                cur.execute("""
                    DELETE FROM banking_receipt_matching_ledger
                    WHERE receipt_id = ANY(%s)
                """, (ids_to_delete,))
                ledger_dup_del = cur.rowcount
                
                # Delete receipts
                cur.execute("""
                    DELETE FROM receipts
                    WHERE receipt_id = ANY(%s)
                """, (ids_to_delete,))
                receipt_dup_del = cur.rowcount
                
                conn.commit()
                print(f"\n[OK] Removed {receipt_dup_del} duplicate receipts, {ledger_dup_del} ledger entries")
        else:
            print(f"\n[DRY-RUN] Would remove {sum(row[3]-1 for row in dup_groups)} duplicate rows")
        
        return len(artifact_rows), len(dup_groups)
    
    except Exception as e:
        if not dry_run:
            conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Dedup receipts (remove QB artifacts)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--write', action='store_true', help='Write to database')
    args = parser.parse_args()
    
    if not args.write:
        args.dry_run = True
    
    artifacts, dups = dedup_receipts(dry_run=args.dry_run)
    
    print("\n" + "="*80)
    print("NEXT: Re-export receipt_lookup_and_entry_2012.xlsx")
    print("="*80)

if __name__ == '__main__':
    main()

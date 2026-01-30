#!/usr/bin/env python3
"""
Link 2012 banking transactions to receipts using date/amount/vendor matching.
Now that categories are applied, we can improve receipt coverage.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    )

def link_banking_to_receipts_2012(dry_run=True):
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("LINKING 2012 BANKING TO RECEIPTS")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLYING CHANGES'}\n")

    # Get unlinked 2012 banking transactions (debits only, categorized)
    cur.execute("""
        SELECT 
            transaction_id, transaction_date, description, debit_amount, category
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND debit_amount IS NOT NULL
          AND debit_amount > 0
          AND category IN ('pos_purchase', 'withdrawal', 'bill_payment')
        ORDER BY transaction_date, transaction_id
    """)
    banking_rows = cur.fetchall()
    
    print(f"Found {len(banking_rows):,} banking transactions to match")

    # Try to match each banking transaction to receipts
    matches = []
    for bank in banking_rows:
        # Look for receipt on same date with matching amount (±$0.02 tolerance)
        cur.execute("""
            SELECT id, vendor_name, gross_amount, category, created_from_banking
            FROM receipts
            WHERE receipt_date = %s
              AND ABS(COALESCE(gross_amount, 0) - %s) <= 0.02
              AND (created_from_banking IS NULL OR created_from_banking = false)
            ORDER BY ABS(COALESCE(gross_amount, 0) - %s)
            LIMIT 1
        """, (bank['transaction_date'], bank['debit_amount'], bank['debit_amount']))
        
        receipt = cur.fetchone()
        if receipt:
            matches.append({
                'transaction_id': bank['transaction_id'],
                'receipt_id': receipt['id'],
                'date': bank['transaction_date'],
                'amount': bank['debit_amount'],
                'bank_desc': bank['description'][:50],
                'receipt_vendor': receipt['vendor_name'],
                'receipt_category': receipt['category']
            })

    print(f"Found {len(matches):,} potential matches ({len(matches)*100//len(banking_rows) if banking_rows else 0}% match rate)\n")

    if matches:
        print("Sample matches:")
        for i, m in enumerate(matches[:10]):
            print(f"  {m['date']} | ${m['amount']:>8.2f} | {m['receipt_vendor']:<30} | {m['bank_desc']}")
        if len(matches) > 10:
            print(f"  ... and {len(matches)-10} more")

    if not dry_run and matches:
        print(f"\n{'=' * 80}")
        print("APPLYING LINKS...")
        print("=" * 80)
        
        # Update receipts to mark as banking-linked
        receipt_ids = [m['receipt_id'] for m in matches]
        cur.execute("""
            UPDATE receipts
            SET created_from_banking = true
            WHERE id = ANY(%s)
        """, (receipt_ids,))
        
        print(f"[OK] Marked {cur.rowcount:,} receipts as banking-linked")
        conn.commit()
    elif dry_run and matches:
        print(f"\n💡 Run with --apply to link {len(matches):,} receipt(s)")

    # Summary stats
    print(f"\n{'=' * 80}")
    print("LINKAGE SUMMARY")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN created_from_banking = true THEN 1 END) as banking_linked,
            COUNT(CASE WHEN created_from_banking IS NULL OR created_from_banking = false THEN 1 END) as manual_unlinked
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
    """)
    stats = cur.fetchone()
    
    print(f"Total 2012 receipts: {stats['total_receipts']:,}")
    print(f"Banking-linked: {stats['banking_linked']:,} ({stats['banking_linked']*100//stats['total_receipts'] if stats['total_receipts'] else 0}%)")
    print(f"Manual/Unlinked: {stats['manual_unlinked']:,} ({stats['manual_unlinked']*100//stats['total_receipts'] if stats['total_receipts'] else 0}%)")

    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description='Link 2012 banking to receipts')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()

    link_banking_to_receipts_2012(dry_run=not args.apply)

if __name__ == '__main__':
    main()

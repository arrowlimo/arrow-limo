#!/usr/bin/env python3
"""
Remove AUDIT system entries from charters table

These are test/system entries that corrupt data flows.
AUDIT002004 has 1 payment ($367.50) which will be orphaned.
AUDIT003379 has no related records.

Creates backup before deletion.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def create_backup(conn):
    """Create backup of AUDIT entries"""
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'audit_entries_backup_{timestamp}'
    
    print(f"\n📦 Creating backup: {backup_table}")
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT *
        FROM charters
        WHERE reserve_number LIKE 'AUDIT%'
    """)
    
    count = cur.rowcount
    conn.commit()
    cur.close()
    
    print(f"   ✓ Backed up {count:,} AUDIT entries")
    return backup_table

def handle_orphaned_payment(conn, dry_run=True):
    """Handle the orphaned payment from AUDIT entries"""
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Find payments linked to AUDIT charter_ids
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, p.amount, p.payment_date, p.charter_id
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        WHERE c.reserve_number LIKE 'AUDIT%'
    """)
    
    payments = cur.fetchall()
    
    if payments:
        print(f"\n[WARN] ORPHANED PAYMENTS ({len(payments)}):")
        for payment in payments:
            print(f"   Payment ID: {payment['payment_id']}")
            print(f"   Amount: ${payment['amount']:.2f}")
            print(f"   Date: {payment['payment_date']}")
            print(f"   Charter ID: {payment['charter_id']}")
        
        if not dry_run:
            # Delete income_ledger entries first
            for payment in payments:
                cur.execute("""
                    DELETE FROM income_ledger
                    WHERE payment_id = %s
                """, (payment['payment_id'],))
            
            # Then delete the orphaned payments
            for payment in payments:
                cur.execute("""
                    DELETE FROM payments
                    WHERE payment_id = %s
                """, (payment['payment_id'],))
            
            conn.commit()
            print(f"   ✓ Deleted {len(payments)} orphaned payment(s) and related ledger entries")
    else:
        print(f"\n✓ No orphaned payments found")
    
    cur.close()

def remove_audit_entries(conn, dry_run=True):
    """Remove AUDIT entries from charters table"""
    
    print("\n" + "=" * 70)
    print("REMOVING AUDIT ENTRIES")
    print("=" * 70)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
    else:
        print("\n✍️ WRITE MODE - Deleting AUDIT entries")
    
    # Get list of AUDIT entries
    cur.execute("""
        SELECT reserve_number, charter_id
        FROM charters
        WHERE reserve_number LIKE 'AUDIT%'
        ORDER BY reserve_number
    """)
    
    audit_entries = cur.fetchall()
    
    print(f"\n📝 Found {len(audit_entries)} AUDIT entries to remove:")
    for entry in audit_entries:
        print(f"   - {entry['reserve_number']} (ID: {entry['charter_id']})")
    
    if not dry_run and len(audit_entries) > 0:
        # Create backup
        backup_table = create_backup(conn)
        
        # Handle orphaned payment
        handle_orphaned_payment(conn, dry_run=False)
        
        # Delete AUDIT entries
        print(f"\n⚙️ Deleting AUDIT entries from charters...")
        cur.execute("""
            DELETE FROM charters
            WHERE reserve_number LIKE 'AUDIT%'
        """)
        
        deleted = cur.rowcount
        conn.commit()
        
        print(f"   ✓ Deleted {deleted:,} AUDIT entries")
        print(f"   ✓ Backup saved as: {backup_table}")
    
    cur.close()
    return len(audit_entries)

def verify_removal(conn):
    """Verify AUDIT entries are removed"""
    
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check for remaining AUDIT entries
    cur.execute("""
        SELECT COUNT(*) as remaining
        FROM charters
        WHERE reserve_number LIKE 'AUDIT%'
    """)
    
    result = cur.fetchone()
    remaining = result['remaining']
    
    print(f"\n✓ Remaining AUDIT entries: {remaining:,}")
    
    if remaining == 0:
        print("   🎉 All AUDIT entries successfully removed!")
    else:
        print("   [WARN] Some AUDIT entries remain - review needed")
    
    # Check for orphaned payments
    cur.execute("""
        SELECT COUNT(*) as cnt
        FROM payments
        WHERE reserve_number LIKE 'AUDIT%'
    """)
    
    orphaned = cur.fetchone()['cnt']
    print(f"\n✓ Orphaned payments: {orphaned:,}")
    
    cur.close()

def main():
    parser = argparse.ArgumentParser(
        description='Remove AUDIT system entries from charters'
    )
    parser.add_argument('--write', action='store_true',
                       help='Apply deletions (default is dry-run)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("AUDIT ENTRY REMOVAL")
    print("=" * 70)
    print("\nThis script removes test/system AUDIT entries from charters table.")
    print("These entries corrupt data flows and should be removed.")
    print("=" * 70)
    
    conn = get_db_connection()
    
    try:
        # Remove AUDIT entries
        count = remove_audit_entries(conn, dry_run=not args.write)
        
        # Verify if write mode
        if args.write and count > 0:
            verify_removal(conn)
        elif count > 0:
            print("\n" + "=" * 70)
            print("🔍 DRY RUN COMPLETE")
            print("=" * 70)
            print(f"\nTo apply deletions, run:")
            print(f"  python {__file__} --write")
        else:
            print("\n✓ No AUDIT entries found!")
        
    finally:
        conn.close()
    
    print("\n" + "=" * 70)
    print("✓ Script complete")
    print("=" * 70)

if __name__ == '__main__':
    main()

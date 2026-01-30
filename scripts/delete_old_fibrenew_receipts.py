"""Delete old Fibrenew receipts with wrong invoice numbering

PROTECTION: This script now includes safeguards and requires explicit confirmation.
Run with --write to apply changes.
"""
import argparse
import psycopg2

# Import protection
try:
    from table_protection import protect_deletion, log_deletion_audit
except ImportError:
    def protect_deletion(table_name, dry_run=True, override_key=None):
        if not dry_run:
            raise Exception(f"🛑 PROTECTED: Cannot delete from {table_name}")
    def log_deletion_audit(table_name, row_count, condition=None, script_name=None):
        pass

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply deletions (default is dry-run)')
    parser.add_argument('--override-key', help='Override key for protected table')
    args = parser.parse_args()

    cn = psycopg2.connect(**DB)
    try:
        cur = cn.cursor()
        
        # Check what would be deleted
        cur.execute("""
            SELECT COUNT(*) FROM receipts 
            WHERE source_reference LIKE 'FIBRENEW-8487-%' 
               OR source_reference LIKE 'FIBRENEW-8691-%' 
               OR source_reference LIKE 'FIBRENEW-8743-%'
        """)
        count = cur.fetchone()[0]
        
        print(f"Found {count} old Fibrenew receipts with wrong numbering")
        
        if not args.write:
            print("🔒 DRY-RUN: No changes made. Add --write to apply.")
            return
        
        # Apply protection check
        try:
            protect_deletion('receipts', dry_run=False, override_key=args.override_key)
        except Exception as e:
            print(f"\n{e}")
            return
        
        cur.execute("""
            DELETE FROM receipts 
            WHERE source_reference LIKE 'FIBRENEW-8487-%' 
               OR source_reference LIKE 'FIBRENEW-8691-%' 
               OR source_reference LIKE 'FIBRENEW-8743-%'
        """)
        deleted = cur.rowcount
        cn.commit()
        
        # Log the deletion
        log_deletion_audit('receipts', deleted, 
                         condition="FIBRENEW wrong numbering (8487, 8691, 8743)",
                         script_name='delete_old_fibrenew_receipts.py')
        
        print(f"✓ Deleted {deleted} old receipts")
    finally:
        cn.close()

if __name__ == '__main__':
    main()


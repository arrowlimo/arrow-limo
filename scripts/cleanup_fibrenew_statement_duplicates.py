"""
Remove statement-based duplicates for specific Fibrenew invoices and prefer detailed invoices.
- Deletes from receipts where source_system='FIBRENEW_STATEMENT' and invoice is in TARGET_INVOICES.
- Safe: prints matches before deletion; requires --write to apply.

PROTECTION: Includes table protection safeguards.
"""
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

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
TARGET_INVOICES = ['8488']  # statement entries to remove

q_find = """
SELECT id, source_system, source_reference, receipt_date, vendor_name, gross_amount, gst_amount, description
FROM receipts
WHERE source_system = 'FIBRENEW_STATEMENT'
  AND (
        source_reference = ANY(%s)
        OR (
            "description" ILIKE ANY(%s)
        )
      )
ORDER BY id
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply deletions')
    args = ap.parse_args()

    refs = [f'FIBRENEW-STATEMENT-{n}' for n in TARGET_INVOICES]
    likes = [f'%Invoice {n}%' for n in TARGET_INVOICES]

    with psycopg2.connect(**DB) as cn:
        with cn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(q_find, (refs, likes))
            rows = cur.fetchall()
            if not rows:
                print('No matching statement duplicates found.')
                return

            print('\nMatches to remove:')
            for r in rows:
                print(f"  id={r['id']} sys={r['source_system']} ref={r['source_reference']} date={r['receipt_date']} gross={r['gross_amount']} gst={r['gst_amount']} desc={r['description']}")

            if args.write:
                # Apply protection check
                try:
                    protect_deletion('receipts', dry_run=False)
                except Exception as e:
                    print(f"\n{e}")
                    return
                
                ids = [r['id'] for r in rows]
                cur.execute('DELETE FROM receipts WHERE id = ANY(%s)', (ids,))
                deleted_count = cur.rowcount
                
                # Log the deletion
                log_deletion_audit('receipts', deleted_count, 
                                 condition=f"FIBRENEW_STATEMENT invoices {TARGET_INVOICES}",
                                 script_name='cleanup_fibrenew_statement_duplicates.py')
                
                print(f"\nDeleted {deleted_count} rows.")
            else:
                print('\nDry-run only. Re-run with --write to delete.')

if __name__ == '__main__':
    main()

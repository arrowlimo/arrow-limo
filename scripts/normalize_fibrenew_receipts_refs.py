"""
Normalize Fibrenew receipts: remove old suffixed references (e.g., FIBRENEW-8487-RENT/UTILITIES)
when an unsuffixed normalized reference exists for the same invoice/date/amount.

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

TARGET = [
    ('FIBRENEW-8487-RENT', 'FIBRENEW-8487'),
    ('FIBRENEW-8487-UTILITIES', 'FIBRENEW-8488'),
]

q_find_pairs = """
SELECT old.id as old_id, old.source_reference as old_ref, old.receipt_date as old_date,
       old.gross_amount as old_gross, old.gst_amount as old_gst,
       new.id as new_id, new.source_reference as new_ref, new.receipt_date as new_date,
       new.gross_amount as new_gross, new.gst_amount as new_gst
FROM receipts old
JOIN receipts new ON (
    new.source_reference = %s
    AND new.receipt_date = old.receipt_date
    AND new.gross_amount = old.gross_amount
    AND new.gst_amount = old.gst_amount
)
WHERE old.source_reference = %s
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply deletions')
    args = ap.parse_args()

    with psycopg2.connect(**DB) as cn:
        with cn.cursor(cursor_factory=RealDictCursor) as cur:
            victims = []
            for old_ref, new_ref in TARGET:
                cur.execute(q_find_pairs, (new_ref, old_ref))
                for r in cur.fetchall():
                    victims.append(r['old_id'])
                    print(f"Matched pair: old {r['old_id']} {old_ref} -> keep {r['new_id']} {new_ref} (date {r['old_date']} gross {r['old_gross']} gst {r['old_gst']})")

            if not victims:
                print('No old suffixed references found to remove.')
                return

            if args.write:
                # Apply protection check
                try:
                    protect_deletion('receipts', dry_run=False)
                except Exception as e:
                    print(f"\n{e}")
                    return
                
                cur.execute('DELETE FROM receipts WHERE id = ANY(%s)', (victims,))
                deleted_count = cur.rowcount
                
                # Log the deletion
                log_deletion_audit('receipts', deleted_count,
                                 condition=f"Fibrenew suffixed refs normalization (ids: {victims[:10]}...)",
                                 script_name='normalize_fibrenew_receipts_refs.py')
                
                print(f"Deleted {deleted_count} old suffixed receipts.")
            else:
                print(f"Dry-run: would delete ids {victims}")

if __name__ == '__main__':
    main()

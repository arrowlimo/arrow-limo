#!/usr/bin/env python
"""Apply GL 6900 remapping with dry-run support."""
import psycopg2, os, json, sys
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD',os.environ.get("DB_PASSWORD"))

DRY_RUN = '--dry-run' in sys.argv

GL_MAPPINGS = {
    'Unknown': '9999',
    'Banking': '5400',
    'Driver Payment': '5000',
    'Income - Card Payments': '4100',
    '(uncategorized)': '9999',
    'Taxes': '2200',
    'Office Staff': '5100',
    'Accounting': '6200',
    'Personal Draws': '3500',
    'Bank Fees': '5400',
}

def backup_affected(cur):
    """Backup all GL 6900 receipts before remapping."""
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, gl_account_code
        FROM receipts
        WHERE gl_account_code = '6900'
        ORDER BY category, receipt_date
    """)
    rows = cur.fetchall()
    backup_data = []
    for r in rows:
        backup_data.append({
            "receipt_id": r[0],
            "receipt_date": str(r[1]),
            "vendor_name": r[2],
            "gross_amount": str(r[3]),
            "category": r[4],
            "old_gl_code": r[5]
        })
    
    fname = f"gl_6900_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, 'w') as f:
        json.dump(backup_data, f, indent=2)
    return fname, len(backup_data)

def apply_remapping(cur, dry_run=False):
    """Apply the GL code remapping based on category."""
    updates = 0
    
    # Handle uncategorized separately (NULL category)
    cur.execute("""
        SELECT receipt_id
        FROM receipts
        WHERE gl_account_code = '6900' AND category IS NULL
    """)
    uncategorized_ids = [r[0] for r in cur.fetchall()]
    
    if not dry_run and uncategorized_ids:
        cur.execute(
            "UPDATE receipts SET gl_account_code = %s WHERE receipt_id = ANY(%s)",
            ('9999', uncategorized_ids)
        )
        updates += cur.rowcount
    
    # Handle other categories
    for cat, new_gl in GL_MAPPINGS.items():
        if cat == '(uncategorized)':
            continue  # Already handled above
        
        cur.execute(
            "SELECT COUNT(*) FROM receipts WHERE gl_account_code = '6900' AND category = %s",
            (cat,)
        )
        cnt = cur.fetchone()[0]
        
        if not dry_run and cnt > 0:
            cur.execute(
                "UPDATE receipts SET gl_account_code = %s WHERE gl_account_code = '6900' AND category = %s",
                (new_gl, cat)
            )
            updates += cur.rowcount
        
        print(f"  {cnt:4d} records | {cat:25s} → GL {new_gl}")
    
    return updates

def verify_remapping(cur):
    """Verify all GL 6900 entries have been remapped."""
    cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '6900'")
    remaining = cur.fetchone()[0]
    return remaining

def main():
    print("=" * 100)
    print("APPLY GL 6900 REMAPPING")
    print("=" * 100)
    print(f"Dry-run: {DRY_RUN}\n")
    
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Backup
    backup_file, backup_count = backup_affected(cur)
    print(f"✅ Backup: {backup_file} ({backup_count} receipts)")
    
    if DRY_RUN:
        print("\n📋 Proposed remapping (dry-run):")
        apply_remapping(cur, dry_run=True)
        print("\nDry-run mode: no changes applied.")
    else:
        print("\n⚡ Applying remapping:")
        updated = apply_remapping(cur, dry_run=False)
        conn.commit()
        print(f"\n✅ Updated {updated} receipts")
        
        remaining = verify_remapping(cur)
        print(f"✅ Verification: {remaining} receipts remain in GL 6900 (should be 0)")
        
        if remaining == 0:
            print("\n✅ Remapping complete!")
    
    cur.close(); conn.close()

if __name__ == '__main__':
    main()

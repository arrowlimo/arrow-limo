#!/usr/bin/env python
"""
Cancel charter 016417:
  - DELETE all charter_charges for 016417
  - UPDATE charters SET cancelled=TRUE, status='Cancelled', total_amount_due=0, balance=0
  - Backup charges before deletion via table_protection
"""
import psycopg2
import argparse
import sys
sys.path.insert(0, 'l:/limo')
from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit

parser = argparse.ArgumentParser(description='Cancel charter 016417 and remove all charges.')
parser.add_argument('--write', action='store_true', help='Apply changes; default is dry-run.')
parser.add_argument('--override-key', default='', help='Override key for protected deletion.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

reserve_number = '016417'

# 1) Verify charter exists
cur.execute("SELECT reserve_number, status, cancelled, total_amount_due, paid_amount, balance FROM charters WHERE reserve_number=%s", (reserve_number,))
charter = cur.fetchone()
if not charter:
    print(f"Charter {reserve_number} not found.")
    cur.close(); conn.close(); exit(1)

print(f"CHARTER BEFORE: {charter}")

# 2) Fetch charges
cur.execute("SELECT charge_id, description, amount FROM charter_charges WHERE reserve_number=%s", (reserve_number,))
charges = cur.fetchall()
print(f"\nCHARGES TO DELETE ({len(charges)}):")
for c in charges:
    print(f"  charge_id={c[0]} desc='{c[1]}' amount={c[2]}")

total_charges = sum(c[2] for c in charges)
print(f"\nTotal charges to remove: ${total_charges}")

if not args.write:
    print("\nDRY RUN - no changes made. Use --write to apply.")
    cur.close(); conn.close(); exit(0)

# 3) Protection check for charter_charges deletion
try:
    protect_deletion('charter_charges', dry_run=False, override_key=args.override_key)
except Exception as e:
    print(f"Protection check failed: {e}")
    print("If you are certain, provide --override-key ALLOW_DELETE_CHARTER_CHARGES_20251110")
    cur.close(); conn.close(); exit(1)

# 4) Backup charges
backup_name = create_backup_before_delete(cur, 'charter_charges', condition=f"reserve_number='{reserve_number}'")
print(f"\nBackup created: {backup_name}")

# 5) Delete charges
cur.execute("DELETE FROM charter_charges WHERE reserve_number=%s", (reserve_number,))
deleted_count = cur.rowcount
print(f"Deleted {deleted_count} charge rows.")

# 6) Update charter: set cancelled=TRUE, status='Cancelled', total_amount_due=0, balance=0
cur.execute("""
    UPDATE charters 
    SET cancelled = TRUE,
        status = 'Cancelled',
        total_amount_due = 0,
        balance = 0,
        updated_at = CURRENT_TIMESTAMP
    WHERE reserve_number = %s
""", (reserve_number,))
print(f"Charter {reserve_number} marked as cancelled.")

# 7) Verify final state
cur.execute("SELECT reserve_number, status, cancelled, total_amount_due, paid_amount, balance FROM charters WHERE reserve_number=%s", (reserve_number,))
charter_after = cur.fetchone()
print(f"\nCHARTER AFTER: {charter_after}")

cur.execute("SELECT COUNT(*) FROM charter_charges WHERE reserve_number=%s", (reserve_number,))
charge_count_after = cur.fetchone()[0]
print(f"Charges remaining: {charge_count_after}")

# 8) Log audit
log_deletion_audit('charter_charges', deleted_count, condition=f"reserve_number='{reserve_number}'")

conn.commit()
print("\nChanges committed successfully.")
cur.close(); conn.close()

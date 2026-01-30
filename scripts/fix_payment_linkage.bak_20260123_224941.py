#!/usr/bin/env python3
"""
FIX PAYMENT LINKAGE ISSUES
===========================

Updates payments that are linked ONLY via charter_id to also have reserve_number.
This ensures consistent linkage across the system.

Safety features:
- Dry-run by default (use --apply to commit)
- Creates backup before updates
- Only updates where reserve_number is NULL or empty
- Validates charter_id exists and has valid reserve_number

Usage:
  python fix_payment_linkage.py           # Dry-run
  python fix_payment_linkage.py --apply   # Apply fixes
"""
import os
import sys
import argparse
import psycopg2
from datetime import datetime

parser = argparse.ArgumentParser(description='Fix payment linkage issues')
parser.add_argument('--apply', action='store_true', help='Apply the fixes (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("="*120)
if args.apply:
    print("FIXING PAYMENT LINKAGE (APPLY MODE)")
else:
    print("PAYMENT LINKAGE FIX - DRY RUN")
print("="*120)
print()

# Step 1: Identify payments with charter_id but no reserve_number
print("Analyzing payment linkage...")
cur.execute("""
    SELECT 
        p.payment_id,
        p.charter_id,
        p.reserve_number as current_reserve,
        c.reserve_number as charter_reserve,
        p.amount,
        p.payment_date,
        p.payment_method
    FROM payments p
    INNER JOIN charters c ON p.charter_id = c.charter_id
    WHERE p.charter_id IS NOT NULL
      AND (p.reserve_number IS NULL OR p.reserve_number = '')
      AND c.reserve_number IS NOT NULL
      AND c.reserve_number != ''
    ORDER BY p.payment_date DESC
""")

to_fix = cur.fetchall()
print(f"Found {len(to_fix)} payments with charter_id but missing reserve_number")
print()

if not to_fix:
    print("No linkage issues found. Exiting.")
    cur.close()
    conn.close()
    sys.exit(0)

# Show summary
print("SUMMARY:")
print("-" * 120)
total_amount = sum(row[4] for row in to_fix)
print(f"Payments to update: {len(to_fix):,}")
print(f"Total amount: ${total_amount:,.2f}")
print()

# Show date range
dates = [row[5] for row in to_fix if row[5]]
if dates:
    print(f"Date range: {min(dates)} to {max(dates)}")
    print()

# Show sample
print("SAMPLE OF CHANGES (first 20):")
print(f"{'Payment ID':<12} {'Charter ID':<12} {'Current Res':<15} {'Will Set To':<15} {'Amount':<12} {'Date':<12}")
print("-" * 120)
for row in to_fix[:20]:
    pid, cid, curr_res, charter_res, amount, pdate, method = row
    print(f"{pid:<12} {cid:<12} {curr_res or 'NULL':<15} {charter_res:<15} ${amount:>10,.2f} {str(pdate):<12}")

print()

# Step 2: Create backup if applying
if args.apply:
    backup_name = f"payments_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_name}...")
    
    cur.execute(f"""
        CREATE TABLE {backup_name} AS 
        SELECT * FROM payments 
        WHERE payment_id IN (
            SELECT p.payment_id
            FROM payments p
            INNER JOIN charters c ON p.charter_id = c.charter_id
            WHERE p.charter_id IS NOT NULL
              AND (p.reserve_number IS NULL OR p.reserve_number = '')
              AND c.reserve_number IS NOT NULL
              AND c.reserve_number != ''
        )
    """)
    backup_count = cur.rowcount
    conn.commit()
    print(f"✓ Backed up {backup_count} payments to {backup_name}")
    print()

# Step 3: Apply fixes
if args.apply:
    print("="*120)
    print("APPLYING FIXES...")
    print("="*120)
    print()
    
    updated = 0
    errors = []
    
    for pid, cid, curr_res, charter_res, amount, pdate, method in to_fix:
        try:
            cur.execute("""
                UPDATE payments
                SET reserve_number = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            """, (charter_res, pid))
            
            updated += 1
            
            if updated % 100 == 0:
                print(f"  Updated {updated}/{len(to_fix)} payments...")
                
        except Exception as e:
            errors.append((pid, str(e)))
            print(f"  ✗ Error updating payment {pid}: {e}")
    
    if errors:
        print(f"\n[WARN]  {len(errors)} errors occurred:")
        for pid, error in errors[:10]:
            print(f"    Payment {pid}: {error}")
    
    # Commit
    conn.commit()
    print()
    print(f"✓ Successfully updated {updated} payments")
    print()
    
    # Verify
    print("VERIFYING FIXES...")
    cur.execute("""
        SELECT COUNT(*)
        FROM payments p
        INNER JOIN charters c ON p.charter_id = c.charter_id
        WHERE p.charter_id IS NOT NULL
          AND (p.reserve_number IS NULL OR p.reserve_number = '')
          AND c.reserve_number IS NOT NULL
          AND c.reserve_number != ''
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("[OK] VERIFICATION PASSED - All linkage issues resolved!")
    else:
        print(f"[WARN]  {remaining} linkage issues still remain")
    
    # Check for consistency
    print()
    print("CHECKING LINKAGE CONSISTENCY...")
    cur.execute("""
        SELECT COUNT(*)
        FROM payments p
        INNER JOIN charters c ON p.charter_id = c.charter_id
        WHERE p.reserve_number != c.reserve_number
    """)
    
    inconsistent = cur.fetchone()[0]
    
    if inconsistent == 0:
        print("[OK] All payments with charter_id have matching reserve_number")
    else:
        print(f"[WARN]  {inconsistent} payments have mismatched charter_id/reserve_number")
    
    print()
    print("="*120)
    print("FIX COMPLETE")
    print("="*120)
    print()
    print(f"Backup table: {backup_name}")
    print(f"Updated payments: {updated}")
    print(f"Total amount: ${total_amount:,.2f}")
    
else:
    print("="*120)
    print("DRY RUN COMPLETE - No changes made")
    print("="*120)
    print()
    print("To apply these fixes, run:")
    print("  python fix_payment_linkage.py --apply")
    print()
    print("This will:")
    print(f"  1. Create backup table with {len(to_fix)} payment records")
    print(f"  2. Update reserve_number for {len(to_fix)} payments")
    print("  3. Set updated_at timestamp")
    print("  4. Verify all linkages are consistent")

cur.close()
conn.close()

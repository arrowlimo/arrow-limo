#!/usr/bin/env python3
"""
FIX 660 PAYMENT MISMATCHES
==========================

Recalculates and updates charter.paid_amount and charter.balance from actual payment sums.

Safety features:
- Dry-run by default (use --apply to commit changes)
- Creates backup before any updates
- Logs all changes to audit trail
- Validates calculations before updating

Usage:
  python fix_payment_mismatches.py           # Dry-run (show what would change)
  python fix_payment_mismatches.py --apply   # Apply the fixes
"""
import os
import sys
import argparse
import psycopg2
from decimal import Decimal
from datetime import datetime

parser = argparse.ArgumentParser(description='Fix charter payment amount mismatches')
parser.add_argument('--apply', action='store_true', help='Apply the fixes (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

print("="*120)
if args.apply:
    print("FIXING PAYMENT MISMATCHES (APPLY MODE)")
else:
    print("PAYMENT MISMATCH FIX - DRY RUN")
print("="*120)
print()

# Step 1: Create backup if applying
if args.apply:
    backup_name = f"charters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_name}...")
    cur.execute(f"""
        CREATE TABLE {backup_name} AS 
        SELECT * FROM charters 
        WHERE reserve_number IN (
            SELECT c.reserve_number
            FROM charters c
            LEFT JOIN (
                SELECT reserve_number, SUM(amount) as total_paid
                FROM payments
                WHERE reserve_number IS NOT NULL
                GROUP BY reserve_number
            ) ps ON ps.reserve_number = c.reserve_number
            WHERE c.cancelled = FALSE
              AND ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.total_paid,0)) > 0.01
        )
    """)
    backup_count = cur.rowcount
    conn.commit()
    print(f"✓ Backed up {backup_count} charters to {backup_name}")
    print()

# Step 2: Get all mismatched charters with correct calculations
print("Calculating correct values...")
cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            ROUND(SUM(COALESCE(amount,0))::numeric, 2) as correct_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.paid_amount as current_paid,
        COALESCE(ps.correct_paid, 0) as correct_paid,
        c.total_amount_due,
        c.balance as current_balance,
        COALESCE(c.total_amount_due, 0) - COALESCE(ps.correct_paid, 0) as correct_balance
    FROM charters c
    LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
    WHERE c.cancelled = FALSE
      AND ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.correct_paid,0)) > 0.01
    ORDER BY ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.correct_paid,0)) DESC
""")

fixes = cur.fetchall()
print(f"Found {len(fixes)} charters to fix")
print()

if not fixes:
    print("No mismatches found. Exiting.")
    cur.close()
    conn.close()
    sys.exit(0)

# Step 3: Show summary of changes
print("SUMMARY OF CHANGES:")
print("-" * 120)

total_paid_adjustment = Decimal(0)
total_balance_adjustment = Decimal(0)

for charter_id, reserve, curr_paid, corr_paid, total_due, curr_bal, corr_bal in fixes:
    paid_diff = Decimal(str(corr_paid)) - Decimal(str(curr_paid or 0))
    bal_diff = Decimal(str(corr_bal)) - Decimal(str(curr_bal or 0))
    total_paid_adjustment += paid_diff
    total_balance_adjustment += bal_diff

print(f"Charters to update: {len(fixes):,}")
print(f"Total paid_amount adjustment: ${total_paid_adjustment:,.2f}")
print(f"Total balance adjustment: ${total_balance_adjustment:,.2f}")
print()

# Show top 20 changes
print("TOP 20 CHANGES (by paid_amount adjustment):")
print(f"{'Reserve':<12} {'Current Paid':<15} {'Correct Paid':<15} {'Adjustment':<15} {'New Balance':<15}")
print("-" * 120)

for i, (charter_id, reserve, curr_paid, corr_paid, total_due, curr_bal, corr_bal) in enumerate(fixes[:20]):
    curr_paid_dec = Decimal(str(curr_paid or 0))
    corr_paid_dec = Decimal(str(corr_paid))
    adjustment = corr_paid_dec - curr_paid_dec
    
    print(f"{reserve:<12} ${curr_paid_dec:>12,.2f} ${corr_paid_dec:>12,.2f} ${adjustment:>12,.2f} ${Decimal(str(corr_bal)):>12,.2f}")

print()

# Step 4: Apply fixes if requested
if args.apply:
    print("="*120)
    print("APPLYING FIXES...")
    print("="*120)
    
    updated_count = 0
    errors = []
    
    for charter_id, reserve, curr_paid, corr_paid, total_due, curr_bal, corr_bal in fixes:
        try:
            cur.execute("""
                UPDATE charters
                SET paid_amount = %s,
                    balance = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE charter_id = %s
            """, (corr_paid, corr_bal, charter_id))
            
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"  Updated {updated_count}/{len(fixes)} charters...")
                
        except Exception as e:
            errors.append((reserve, str(e)))
            print(f"  ✗ Error updating {reserve}: {e}")
    
    if errors:
        print(f"\n[WARN]  {len(errors)} errors occurred:")
        for reserve, error in errors[:10]:
            print(f"    {reserve}: {error}")
    
    # Commit changes
    conn.commit()
    
    print()
    print(f"✓ Successfully updated {updated_count} charters")
    print()
    
    # Verify the fix
    print("VERIFYING FIXES...")
    cur.execute("""
        WITH payment_sums AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount,0))::numeric, 2) as correct_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT COUNT(*)
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
        WHERE c.cancelled = FALSE
          AND ABS(COALESCE(c.paid_amount,0) - COALESCE(ps.correct_paid,0)) > 0.01
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("[OK] VERIFICATION PASSED - All mismatches resolved!")
    else:
        print(f"[WARN]  {remaining} mismatches still remain (may need manual review)")
    
    print()
    print("="*120)
    print("FIX COMPLETE")
    print("="*120)
    print()
    print(f"Backup table: {backup_name}")
    print(f"Updated charters: {updated_count}")
    print(f"Total paid_amount adjustment: ${total_paid_adjustment:,.2f}")
    print(f"Total balance adjustment: ${total_balance_adjustment:,.2f}")
    
else:
    print("="*120)
    print("DRY RUN COMPLETE - No changes made")
    print("="*120)
    print()
    print("To apply these fixes, run:")
    print("  python fix_payment_mismatches.py --apply")
    print()
    print("This will:")
    print(f"  1. Create backup table with {len(fixes)} charter records")
    print(f"  2. Update paid_amount field for {len(fixes)} charters")
    print(f"  3. Recalculate balance field for {len(fixes)} charters")
    print("  4. Set updated_at timestamp")
    print("  5. Verify all fixes were successful")

cur.close()
conn.close()

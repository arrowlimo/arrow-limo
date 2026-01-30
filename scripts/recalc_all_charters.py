#!/usr/bin/env python3
"""
Recalculate paid_amount and balance for ALL charters (including cancelled).
Based on actual payment sums by reserve_number.
"""

import psycopg2
from datetime import datetime
import argparse

parser = argparse.ArgumentParser(description='Recalculate ALL charter amounts')
parser.add_argument('--write', action='store_true', help='Apply fixes (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("=" * 80)
print("RECALCULATE ALL CHARTER PAID_AMOUNT AND BALANCE")
print("=" * 80)

# Step 1: Find all charters with mismatched paid_amount
cur.execute("""
    WITH payment_sums AS (
        SELECT 
            reserve_number,
            ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.paid_amount as current_paid,
        COALESCE(ps.actual_paid, 0) as correct_paid,
        c.total_amount_due,
        c.balance as current_balance,
        COALESCE(c.total_amount_due, 0) - COALESCE(ps.actual_paid, 0) as correct_balance,
        c.cancelled
    FROM charters c
    LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
    WHERE ABS(COALESCE(c.paid_amount, 0) - COALESCE(ps.actual_paid, 0)) > 0.01
    ORDER BY c.cancelled DESC, ABS(COALESCE(c.paid_amount, 0) - COALESCE(ps.actual_paid, 0)) DESC
""")

fixes = cur.fetchall()

print(f"\n📊 FOUND {len(fixes)} CHARTERS TO FIX")

cancelled_count = sum(1 for f in fixes if f[7])
active_count = len(fixes) - cancelled_count

print(f"   Active charters: {active_count}")
print(f"   Cancelled charters: {cancelled_count}")

if len(fixes) > 0:
    print(f"\n📋 TOP 20 CHARTERS TO FIX:")
    print(f"{'Reserve':<10} {'Cancelled':<10} {'Current':<12} {'Correct':<12} {'Adjustment':<12}")
    print("-" * 70)
    
    for i, f in enumerate(fixes[:20]):
        reserve, current_paid, correct_paid, cancelled = f[1], f[2], f[3], f[7]
        adjustment = correct_paid - (current_paid or 0)
        status = "CANCELLED" if cancelled else "Active"
        print(f"{reserve:<10} {status:<10} ${current_paid or 0:>10,.2f} ${correct_paid:>10,.2f} ${adjustment:>10,.2f}")

if args.write:
    print(f"\n📦 CREATING BACKUP...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT c.*
        FROM charters c
        WHERE c.reserve_number IN (
            SELECT reserve_number FROM (VALUES {','.join(f"('{f[1]}')" for f in fixes[:1000])}) AS v(reserve_number)
        )
    """)
    
    backup_count = cur.rowcount
    conn.commit()
    print(f"   ✓ Backed up {backup_count} charters to {backup_table}")
    
    print(f"\n🔧 UPDATING CHARTERS...")
    
    updated = 0
    for charter in fixes:
        charter_id, reserve, current_paid, correct_paid, total_due, current_balance, correct_balance, cancelled = charter
        
        cur.execute("""
            UPDATE charters
            SET paid_amount = %s,
                balance = %s
            WHERE charter_id = %s
        """, (correct_paid, correct_balance, charter_id))
        
        updated += 1
        if updated % 1000 == 0:
            print(f"   Updated {updated}/{len(fixes)}...")
    
    conn.commit()
    
    print(f"\n[OK] UPDATED {updated} CHARTERS")
    
    # Verify
    cur.execute("""
        WITH payment_sums AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT COUNT(*)
        FROM charters c
        LEFT JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
        WHERE ABS(COALESCE(c.paid_amount, 0) - COALESCE(ps.actual_paid, 0)) > 0.01
    """)
    
    remaining = cur.fetchone()[0]
    
    print(f"\n📊 VERIFICATION:")
    print(f"   Remaining mismatches: {remaining}")
    
    if remaining == 0:
        print(f"   [OK] ALL CHARTERS FIXED!")
    else:
        print(f"   [WARN] {remaining} charters still have mismatches")

else:
    print(f"\n🔍 DRY RUN COMPLETE")
    print(f"\nTo apply fixes, run:")
    print(f"  python {__file__} --write")

print("\n" + "=" * 80)
print("✓ Script complete")
print("=" * 80)

cur.close()
conn.close()

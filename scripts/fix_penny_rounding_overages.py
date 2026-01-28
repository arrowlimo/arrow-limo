#!/usr/bin/env python3
"""
Fix 7 penny rounding overages by updating total_amount_due to match charge_sum.
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
conn.autocommit = False
cur = conn.cursor()

# The 7 reserves with penny rounding overages
RESERVES = [
    '016086',  # $1,953.92 → $1,953.93 (+$0.01)
    '016358',  # $335.01 → $335.02 (+$0.01)
    '005061',  # $254.45 → $254.46 (+$0.01)
    '001699',  # $206.24 → $206.25 (+$0.01)
    '018904',  # $2,541.75 → $2,541.76 (+$0.01)
    '006984',  # $799.99 → $800.00 (+$0.01)
    '005060',  # $254.45 → $254.46 (+$0.01)
]

print("="*80)
print("FIX PENNY ROUNDING OVERAGES")
print("="*80)

# Create backup
backup_file = f"reports/penny_rounding_overages_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
print(f"\nCreating backup: {backup_file}")

cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = ANY(%s)
    ORDER BY reserve_number
""", (RESERVES,))

with open(backup_file, 'w') as f:
    f.write("reserve_number,old_total_amount_due,paid_amount,old_balance\n")
    for row in cur.fetchall():
        f.write(f"{row[0]},{row[1]},{row[2]},{row[3]}\n")

print(f"✅ Backup saved")

# Update each charter
print("\nUpdating charters:")
print("-"*80)

updates = []
for reserve in RESERVES:
    # Get current values and charge sum
    cur.execute("""
        SELECT 
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            COALESCE(SUM(cc.amount), 0) as charge_sum
        FROM charters c
        LEFT JOIN charter_charges cc ON c.reserve_number = cc.reserve_number
        WHERE c.reserve_number = %s
        GROUP BY c.reserve_number, c.total_amount_due, c.paid_amount, c.balance
    """, (reserve,))
    
    row = cur.fetchone()
    if not row:
        print(f"  ❌ {reserve} - not found")
        continue
    
    old_total, paid, old_balance, charge_sum = row
    new_total = charge_sum
    new_balance = new_total - paid
    
    # Update
    cur.execute("""
        UPDATE charters
        SET total_amount_due = %s,
            balance = %s
        WHERE reserve_number = %s
    """, (new_total, new_balance, reserve))
    
    print(f"  {reserve}: ${old_total:,.2f} → ${new_total:,.2f} (balance ${old_balance:,.2f} → ${new_balance:,.2f})")
    updates.append((reserve, old_total, new_total, old_balance, new_balance))

# Commit
try:
    conn.commit()
    print(f"\n✅ Updated {len(updates)} charters")
    
    # Verify
    print("\nVerification:")
    print("-"*80)
    cur.execute("""
        WITH charge_sums AS (
            SELECT 
                c.reserve_number,
                c.total_amount_due,
                COALESCE(SUM(cc.amount), 0) as charge_sum
            FROM charters c
            LEFT JOIN charter_charges cc ON c.reserve_number = cc.reserve_number
            WHERE c.reserve_number = ANY(%s)
            GROUP BY c.reserve_number, c.total_amount_due
        )
        SELECT 
            reserve_number,
            total_amount_due,
            charge_sum,
            (charge_sum - total_amount_due) as diff
        FROM charge_sums
        ORDER BY reserve_number
    """, (RESERVES,))
    
    all_match = True
    for row in cur.fetchall():
        reserve, total, charges, diff = row
        if abs(diff) < 0.001:
            print(f"  ✅ {reserve}: total=${total:,.2f}, charges=${charges:,.2f}, diff=${diff:,.2f}")
        else:
            print(f"  ❌ {reserve}: total=${total:,.2f}, charges=${charges:,.2f}, diff=${diff:,.2f}")
            all_match = False
    
    if all_match:
        print(f"\n✅ All overages eliminated!")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    print("Transaction rolled back")

finally:
    cur.close()
    conn.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Charters updated: {len(updates)}")
print(f"Backup: {backup_file}")
print(f"All changes: Penny rounding ($0.01) to align total_amount_due with charge_sum")

import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Categorizing 'Rounding Adjustments'...\n")

# Get all rounding adjustments and categorize them
cur.execute("""
    SELECT charge_id, reserve_number, amount
    FROM charter_charges
    WHERE description = 'Rounding Adjustment'
    ORDER BY amount
""")

all_adjustments = cur.fetchall()

# Categorize
penny_rounding = [r for r in all_adjustments if r[2] < 1.00]
small_adjustments = [r for r in all_adjustments if 1.00 <= r[2] < 100.00]
large_charges = [r for r in all_adjustments if r[2] >= 100.00]

print(f"Total adjustments: {len(all_adjustments)}\n")
print(f"Penny rounding (< $1.00):     {len(penny_rounding):>4} adjustments")
print(f"Small adjustments ($1-$99):   {len(small_adjustments):>4} adjustments")
print(f"Large charges (>= $100):      {len(large_charges):>4} adjustments")

print(f"\n{'='*70}")
print("CORRECTING DESCRIPTIONS")
print(f"{'='*70}\n")

# Update large charges to say "Unfilled Charge"
for charge_id, reserve, amount in large_charges:
    cur.execute("""
        UPDATE charter_charges
        SET description = 'Unfilled Charge'
        WHERE charge_id = %s
    """, (charge_id,))

conn.commit()
print(f"✅ Updated {len(large_charges)} large charges from 'Rounding Adjustment' to 'Unfilled Charge'")

# Update small adjustments to "Service Fee Adjustment"
for charge_id, reserve, amount in small_adjustments:
    cur.execute("""
        UPDATE charter_charges
        SET description = 'Service Fee Adjustment'
        WHERE charge_id = %s
    """, (charge_id,))

conn.commit()
print(f"✅ Updated {len(small_adjustments)} small adjustments to 'Service Fee Adjustment'")

print(f"✅ Kept {len(penny_rounding)} penny roundings as 'Rounding Adjustment'")

# Summary by category
print(f"\n{'='*70}")
print("SUMMARY BY CATEGORY")
print(f"{'='*70}\n")

cur.execute("""
    SELECT description, COUNT(*) as count, MIN(amount) as min_amt, MAX(amount) as max_amt, SUM(amount) as total
    FROM charter_charges
    WHERE description IN ('Rounding Adjustment', 'Service Fee Adjustment', 'Unfilled Charge')
    GROUP BY description
    ORDER BY description
""")

for row in cur.fetchall():
    print(f"{row[0]:<30} {row[1]:>6} charges | ${row[2]:>8.2f} to ${row[3]:>8.2f} | Total: ${row[4]:>10.2f}")

cur.close()
conn.close()

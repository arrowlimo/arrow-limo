"""
Find payments that are wildly mismatched by date to their charter.
If payment_date is years before/after charter_date, it's likely wrong.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("FIND PAYMENTS WITH DATE MISMATCH TO CHARTER")
print("=" * 80)

# Find payments where date is way off from charter date
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        p.payment_id,
        p.payment_date,
        p.amount,
        ABS(p.payment_date - c.charter_date) as days_diff,
        p.notes
    FROM payments p
    JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.payment_date IS NOT NULL
      AND c.charter_date IS NOT NULL
      AND ABS(p.payment_date - c.charter_date) > 365
      AND p.notes LIKE '%AUTO-MATCHED%'
    ORDER BY ABS(p.payment_date - c.charter_date) DESC
""")

mismatches = cur.fetchall()

if not mismatches:
    print("\n✓ No date mismatches found")
else:
    print(f"\n[WARN]  Found {len(mismatches)} payments with >1 year date mismatch")
    
    total_amount = sum(m[4] for m in mismatches)
    print(f"   Total amount: ${total_amount:,.2f}")
    
    print(f"\n📋 TOP 20 DATE MISMATCHES:")
    print(f"\n{'Reserve':<10} {'Charter Date':<12} {'Payment Date':<12} {'Amount':>12} {'Years Off':>10} Notes")
    print("-" * 110)
    
    for i, (reserve, charter_date, payment_id, payment_date, amount, days_diff, notes) in enumerate(mismatches[:20]):
        years_off = days_diff / 365
        notes_short = (notes[:40] + '...') if notes and len(notes) > 40 else (notes or '')
        print(f"{reserve:<10} {str(charter_date):<12} {str(payment_date):<12} ${amount:>10,.2f} {years_off:>9.1f}y {notes_short}")

# Get total by charter
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        COUNT(p.payment_id) as wrong_payments,
        SUM(p.amount) as wrong_amount
    FROM charters c
    JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE p.payment_date IS NOT NULL
      AND c.charter_date IS NOT NULL
      AND ABS(p.payment_date - c.charter_date) > 365
      AND p.notes LIKE '%AUTO-MATCHED%'
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance
    ORDER BY SUM(p.amount) DESC
""")

by_charter = cur.fetchall()

print(f"\n{'='*80}")
print(f"CHARTERS WITH MISMATCHED PAYMENTS")
print("=" * 80)

print(f"\n{'Reserve':<10} {'Charter':<12} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Wrong $':>12} {'Count'}")
print("-" * 100)

for row in by_charter[:20]:
    print(f"{row[0]:<10} {str(row[1]):<12} ${row[2]:>10,.2f} ${row[3]:>10,.2f} ${row[4]:>10,.2f} ${row[6]:>10,.2f} {row[5]:>5}x")

cur.close()
conn.close()

print("\n" + "=" * 80)
print(f"Total mismatched payments: {len(mismatches)}")
print(f"Total mismatched amount: ${sum(m[4] for m in mismatches):,.2f}")
print("=" * 80)

"""
Find payments that were auto-linked multiple times to the same charter.

Pattern: Same (reserve_number, amount, payment_date) appearing multiple times.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("FIND AUTO-LINKED DUPLICATE PAYMENTS")
print("=" * 80)

# Find duplicate payments (same reserve_number, amount, date)
cur.execute("""
    SELECT 
        reserve_number,
        payment_date,
        amount,
        COUNT(*) as duplicate_count,
        ARRAY_AGG(payment_id ORDER BY payment_id) as payment_ids,
        MAX(notes) as sample_notes
    FROM payments
    WHERE reserve_number IS NOT NULL
      AND notes LIKE '%Auto-linked%confidence=%'
    GROUP BY reserve_number, payment_date, amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, amount DESC
""")

duplicates = cur.fetchall()

if not duplicates:
    print("\n✓ No auto-linked duplicates found")
else:
    print(f"\n[WARN]  Found {len(duplicates)} sets of auto-linked duplicates")
    
    total_duplicate_payments = sum(d[3] - 1 for d in duplicates)  # -1 because we keep one
    total_duplicate_amount = sum(d[2] * (d[3] - 1) for d in duplicates)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Duplicate payment records: {total_duplicate_payments}")
    print(f"   Duplicate amount: ${total_duplicate_amount:,.2f}")
    
    print(f"\n📋 TOP 20 DUPLICATE SETS:")
    print(f"\n{'Reserve':<10} {'Date':<12} {'Amount':>12} {'Count':>6} Sample Notes")
    print("-" * 100)
    
    for i, (reserve, pay_date, amount, count, payment_ids, notes) in enumerate(duplicates[:20]):
        notes_short = (notes[:60] + '...') if notes and len(notes) > 60 else (notes or '')
        print(f"{reserve:<10} {str(pay_date):<12} ${amount:>10,.2f} {count:>6}x {notes_short}")
        
        if i < 5:  # Show payment IDs for first 5
            print(f"           Payment IDs: {payment_ids}")

# Check specific charters with most duplicates
print(f"\n{'='*80}")
print("CHARTERS WITH MOST AUTO-LINKED DUPLICATES")
print("=" * 80)

cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        COUNT(p.payment_id) as payment_count,
        COUNT(DISTINCT (p.payment_date, p.amount)) as unique_payments,
        COUNT(p.payment_id) - COUNT(DISTINCT (p.payment_date, p.amount)) as duplicate_count
    FROM charters c
    JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE p.notes LIKE '%Auto-linked%confidence=%'
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance
    HAVING COUNT(p.payment_id) - COUNT(DISTINCT (p.payment_date, p.amount)) > 0
    ORDER BY COUNT(p.payment_id) - COUNT(DISTINCT (p.payment_date, p.amount)) DESC
    LIMIT 20
""")

print(f"\n{'Reserve':<10} {'Date':<12} {'Total':>12} {'Paid':>12} {'Balance':>12} {'Payments':>8} {'Unique':>7} {'Dupes':>6}")
print("-" * 110)

for row in cur.fetchall():
    print(f"{row[0]:<10} {str(row[1]):<12} ${row[2]:>10,.2f} ${row[3]:>10,.2f} ${row[4]:>10,.2f} {row[5]:>8} {row[6]:>7} {row[7]:>6}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("Use remove_auto_linked_duplicates.py to fix these duplicates")
print("=" * 80)

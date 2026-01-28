"""Check remaining doubled payments by import source."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Find charters with approximately 2x payments
cur.execute("""
    WITH payment_totals AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            COUNT(p.payment_id) as payment_count
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.total_amount_due > 0
        GROUP BY c.charter_id
    )
    SELECT reserve_number
    FROM payment_totals
    WHERE ABS(paid_amount - (total_amount_due * 2)) < 1.0
    AND payment_count >= 2
    ORDER BY reserve_number
""")

doubled_reserves = [r[0] for r in cur.fetchall()]

print(f"Total charters with ~2x payments: {len(doubled_reserves)}")
print("\nAnalyzing by import source...")

# Check import sources for each
sources = {
    'aug_5_or_9': 0,
    'oct_13': 0,
    'nov_11_or_13_lms': 0,
    'july_24': 0,
    'mixed': 0,
    'other': 0
}

for reserve in doubled_reserves:
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, created_at::date
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_id
    """, (reserve,))
    
    payments = cur.fetchall()
    created_dates = [p[4] for p in payments]
    keys = [p[3] for p in payments]
    
    # Check sources
    has_aug = any(d.strftime('%Y-%m-%d') in ['2025-08-05', '2025-08-09'] for d in created_dates)
    has_oct = any(d.strftime('%Y-%m-%d') == '2025-10-13' for d in created_dates)
    has_lms = any(k and k.startswith('LMS:') for k in keys)
    has_july = any(d.strftime('%Y-%m-%d') == '2025-07-24' for d in created_dates)
    
    source_count = sum([has_aug, has_oct, has_lms, has_july])
    
    if source_count > 1:
        sources['mixed'] += 1
    elif has_aug:
        sources['aug_5_or_9'] += 1
    elif has_oct:
        sources['oct_13'] += 1
    elif has_lms:
        sources['nov_11_or_13_lms'] += 1
    elif has_july:
        sources['july_24'] += 1
    else:
        sources['other'] += 1

print("\nImport source breakdown:")
for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
    print(f"  {source}: {count}")

# Sample Aug 5/9 cases
print("\n" + "="*80)
print("SAMPLE AUG 5/9 CASES")
print("="*80)

cur.execute("""
    WITH payment_totals AS (
        SELECT 
            c.reserve_number,
            c.total_amount_due,
            c.paid_amount
        FROM charters c
        WHERE c.total_amount_due > 0
        AND ABS(c.paid_amount - (c.total_amount_due * 2)) < 1.0
    )
    SELECT DISTINCT pt.reserve_number
    FROM payment_totals pt
    JOIN payments p ON p.reserve_number = pt.reserve_number
    WHERE p.created_at::date IN ('2025-08-05', '2025-08-09')
    LIMIT 10
""")

for row in cur.fetchall():
    reserve = row[0]
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, created_at
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_id
    """, (reserve,))
    
    payments = cur.fetchall()
    print(f"\nReserve {reserve}: {len(payments)} payments")
    for p in payments:
        print(f"  ID {p[0]}: ${p[1]:,.2f} on {p[2]}, Key: {p[3]}, Created: {p[4]}")

cur.close()
conn.close()

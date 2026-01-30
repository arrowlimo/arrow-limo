"""List the 280 charters that just had charges imported from LMS."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Get charters with newly imported charges (charge_id >= 68273 based on what we saw)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        COUNT(cc.charge_id) as num_charges,
        ROUND(SUM(cc.amount)::numeric, 2) as charges_total
    FROM charters c
    JOIN charter_charges cc ON c.charter_id = cc.charter_id
    WHERE c.charter_id IN (
        SELECT DISTINCT charter_id 
        FROM charter_charges 
        WHERE charge_id >= 68273
    )
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due
    ORDER BY c.reserve_number
""")

rows = cur.fetchall()

print(f"\n{'='*90}")
print(f"280 CHARTERS WITH NEWLY IMPORTED CHARGE BREAKDOWNS FROM LMS")
print(f"{'='*90}\n")

print(f"{'Reserve':<10} {'Date':<12} {'PG Total':<12} {'#':<5} {'LMS Total':<12} {'Match':<6}")
print('-'*90)

matched = 0
discrepancies = []

for r in rows:
    reserve = r[0]
    date = str(r[1]) if r[1] else ''
    pg_total = float(r[2]) if r[2] else 0.0
    num_charges = r[3]
    lms_total = float(r[4]) if r[4] else 0.0
    
    diff = abs(pg_total - lms_total)
    match = '✓' if diff < 0.02 else '⚠'
    
    if diff < 0.02:
        matched += 1
    else:
        discrepancies.append((reserve, pg_total, lms_total, diff))
    
    print(f"{reserve:<10} {date:<12} ${pg_total:>9,.2f} {num_charges:>4} ${lms_total:>9,.2f} {match:<6}")

print('-'*90)
print(f"\nSummary:")
print(f"  Total charters: {len(rows)}")
print(f"  Matched (within $0.02): {matched}")
print(f"  Discrepancies: {len(discrepancies)}")

if discrepancies:
    print(f"\nDiscrepancies requiring review:")
    for reserve, pg, lms, diff in discrepancies:
        print(f"  {reserve}: PG=${pg:.2f} vs LMS=${lms:.2f} (diff ${diff:.2f})")

cur.close()
conn.close()

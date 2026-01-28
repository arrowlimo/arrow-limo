"""Check if any charters across all years still need charge breakdowns."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Find charters with total_amount_due but no charges
cur.execute("""
    SELECT 
        COUNT(*), 
        MIN(charter_date)::text, 
        MAX(charter_date)::text,
        ROUND(SUM(total_amount_due)::numeric, 2)
    FROM charters c
    WHERE c.total_amount_due IS NOT NULL
      AND c.total_amount_due > 0
      AND NOT EXISTS (
          SELECT 1 FROM charter_charges cc
          WHERE cc.charter_id = c.charter_id
      )
""")
row = cur.fetchone()

print("\n" + "="*80)
print("CHARTERS WITH AMOUNT BUT NO CHARGE BREAKDOWN")
print("="*80)

total_count = row[0]
print(f"\nTotal charters missing charges: {total_count}")

if total_count > 0:
    print(f"Date range: {row[1]} to {row[2]}")
    print(f"Total amount: ${float(row[3]):,.2f}")
    
    # Breakdown by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*),
            ROUND(SUM(total_amount_due)::numeric, 2)
        FROM charters c
        WHERE c.total_amount_due IS NOT NULL
          AND c.total_amount_due > 0
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc
              WHERE cc.charter_id = c.charter_id
          )
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    print("\nBreakdown by year:")
    print(f"{'Year':<8} {'Count':<10} {'Total Amount':<15}")
    print("-"*40)
    for r in cur.fetchall():
        year = int(r[0]) if r[0] else 'NULL'
        count = r[1]
        amount = float(r[2]) if r[2] else 0
        print(f"{year:<8} {count:<10} ${amount:>12,.2f}")
    
    # Sample 10 charters
    cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, status, cancelled
        FROM charters c
        WHERE c.total_amount_due IS NOT NULL
          AND c.total_amount_due > 0
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc
              WHERE cc.charter_id = c.charter_id
          )
        ORDER BY charter_date DESC
        LIMIT 10
    """)
    
    print("\nSample of 10 most recent:")
    print(f"{'Reserve':<12} {'Date':<12} {'Amount':<12} {'Status':<15} {'Cancelled':<10}")
    print("-"*70)
    for r in cur.fetchall():
        reserve = r[0]
        date = str(r[1]) if r[1] else ''
        amount = float(r[2]) if r[2] else 0
        status = r[3] or ''
        cancelled = r[4]
        print(f"{reserve:<12} {date:<12} ${amount:>10,.2f} {status:<15} {cancelled}")
else:
    print("\n✓ ALL CHARTERS WITH AMOUNTS HAVE CHARGE BREAKDOWNS!")

cur.close()
conn.close()

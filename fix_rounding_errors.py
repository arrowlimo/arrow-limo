import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get all 10 rounding errors
rounding_errors = [
    ("018494", Decimal("0.01")),
    ("016688", Decimal("0.02")),
    ("018404", Decimal("0.02")),
    ("016245", Decimal("0.30")),
    ("016247", Decimal("0.33")),
    ("018561", Decimal("0.35")),
    ("017069", Decimal("0.43")),
    ("016280", Decimal("0.77")),
    ("016199", Decimal("0.78")),
    ("016383", Decimal("0.88")),
]

print(f"Fixing {len(rounding_errors)} rounding errors...\n")

for reserve, deficit in rounding_errors:
    # Get charter_id
    cur.execute("""
        SELECT charter_id FROM charters WHERE reserve_number = %s
    """, (reserve,))
    result = cur.fetchone()
    
    if not result:
        print(f"⚠️  Charter {reserve} not found")
        continue
    
    charter_id = result[0]
    
    # Insert rounding adjustment
    cur.execute("""
        INSERT INTO charter_charges (charter_id, reserve_number, description, amount, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, (charter_id, reserve, "Rounding Adjustment", float(deficit)))
    conn.commit()
    
    print(f"✅ {reserve}: Added ${float(deficit):.2f} rounding adjustment")

print(f"\n✅ Fixed {len(rounding_errors)} rounding errors")

# Verify final count
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        COUNT(CASE WHEN c.total_amount_due = s.charge_sum THEN 1 END) AS exact_match,
        COUNT(CASE WHEN c.total_amount_due < s.charge_sum THEN 1 END) AS overages,
        COUNT(CASE WHEN c.total_amount_due > 0 AND s.charge_sum < c.total_amount_due THEN 1 END) AS deficits,
        COUNT(*) AS total_charters
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE c.charter_date < '2025-01-01'
""")

row = cur.fetchone()
print(f"\nFinal Pre-2025 Audit (after fixes):")
print(f"  Exact matches: {row[0]:,}")
print(f"  Overages:      {row[1]}")
print(f"  Deficits:      {row[2]}")
print(f"  Total charters: {row[3]:,}")

cur.close()
conn.close()

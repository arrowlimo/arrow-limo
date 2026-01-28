import psycopg2
import os
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Deleting 524 'Unfilled Charge' placeholders...\n")

# Backup first
cur.execute("""
    SELECT charge_id, charter_id, reserve_number, description, amount, created_at
    FROM charter_charges
    WHERE description = 'Unfilled Charge'
    ORDER BY charge_id
""")

unfilled = cur.fetchall()

backup_file = f"L:\\limo\\reports\\unfilled_charges_deleted_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(backup_file, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['charge_id', 'charter_id', 'reserve_number', 'description', 'amount', 'created_at'])
    for row in unfilled:
        w.writerow(row)

print(f"✅ Backup created: {backup_file}")
print(f"   {len(unfilled)} unfilled charges backed up\n")

# Delete them
cur.execute("DELETE FROM charter_charges WHERE description = 'Unfilled Charge'")
deleted = cur.rowcount
conn.commit()

print(f"✅ Deleted {deleted} 'Unfilled Charge' placeholders")

# Verify
cur.execute("""
    WITH sums AS (
        SELECT reserve_number, SUM(amount) AS charge_sum
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    )
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN c.total_amount_due = s.charge_sum THEN 1 END) AS exact_match,
        COUNT(CASE WHEN c.total_amount_due < s.charge_sum THEN 1 END) AS overages,
        COUNT(CASE WHEN c.total_amount_due > 0 AND s.charge_sum < c.total_amount_due THEN 1 END) AS deficits,
        COUNT(CASE WHEN s.charge_sum IS NULL OR s.charge_sum = 0 THEN 1 END) AS zero_charges
    FROM charters c
    LEFT JOIN sums s ON c.reserve_number = s.reserve_number
    WHERE status NOT IN ('cancelled', 'refunded')
""")

result = cur.fetchone()
print(f"\n{'='*70}")
print(f"CHARTER RECONCILIATION STATUS (after deletion)")
print(f"{'='*70}\n")
print(f"Total active charters:        {result[0]:>6,}")
print(f"✅ Exact match:              {result[1]:>6,}  ({100*result[1]/result[0]:.1f}%)")
print(f"Overages:                    {result[2]:>6}")
print(f"Deficits:                    {result[3]:>6}")
print(f"Zero charges (unfilled):     {result[4]:>6}")

print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"Deleted:     {deleted} artificial 'Unfilled Charge' placeholders")
print(f"Retained:    All actual payments and itemized charges")
print(f"Status:      Charters now reflect real transaction data, not artifacts")

cur.close()
conn.close()

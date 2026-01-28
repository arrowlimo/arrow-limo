import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("VERIFYING 524 UNFILLED CHARGES")
print("="*80)
print()

# Get all unfilled charges with charter details
cur.execute("""
    SELECT c.reserve_number, c.status, c.charter_date, c.total_amount_due, c.paid_amount,
           cc.charge_id, cc.amount,
           COUNT(*) OVER (PARTITION BY c.reserve_number) as charge_count
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.description = 'Unfilled Charge'
    ORDER BY c.charter_date, c.reserve_number
    LIMIT 50
""")

rows = cur.fetchall()

print(f"Showing first 50 of 524 unfilled charges:\n")
print(f"{'Reserve':<10} {'Status':<15} {'Date':<12} {'Total Due':>12} {'Paid':>12} {'# Charges':>10}")
print("-" * 80)

prev_reserve = None
for row in rows:
    if row[0] != prev_reserve:
        print(f"{row[0]:<10} {(row[1] or 'NULL'):<15} {str(row[2]):<12} ${row[3]:>11.2f} ${row[4]:>11.2f} {row[7]:>10}")
        prev_reserve = row[0]

# Analyze categories
print("\n" + "="*80)
print("CATEGORIZATION ANALYSIS")
print("="*80)

cur.execute("""
    SELECT 
        COUNT(DISTINCT c.reserve_number) as charter_count,
        c.status,
        COUNT(CASE WHEN c.paid_amount = 0 THEN 1 END) as unpaid,
        COUNT(CASE WHEN c.paid_amount > 0 AND c.balance = 0 THEN 1 END) as paid_in_full,
        COUNT(CASE WHEN c.balance > 0 THEN 1 END) as partial_paid,
        COUNT(CASE WHEN c.balance < 0 THEN 1 END) as overpaid
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.description = 'Unfilled Charge'
    GROUP BY c.status
    ORDER BY charter_count DESC
""")

print(f"\nBy Status:")
print(f"{'Status':<20} {'Count':>8} {'Unpaid':>8} {'Paid Full':>10} {'Partial':>10} {'Overpaid':>10}")
print("-" * 80)

for row in cur.fetchall():
    status = row[1] or 'NULL'
    print(f"{status:<20} {row[0]:>8} {row[2]:>8} {row[3]:>10} {row[4]:>10} {row[5]:>10}")

# Check for zero total charters
print("\n" + "="*80)
print("POTENTIAL ISSUES")
print("="*80)

cur.execute("""
    SELECT COUNT(DISTINCT c.reserve_number) 
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.description = 'Unfilled Charge'
    AND c.total_amount_due = 0
""")

zero_total = cur.fetchone()[0]
print(f"\nCharters with total_amount_due = 0: {zero_total}")

# Check for payments but no other charges
cur.execute("""
    SELECT COUNT(DISTINCT c.reserve_number)
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.description = 'Unfilled Charge'
    AND (
        SELECT COUNT(*) FROM charter_charges WHERE reserve_number = c.reserve_number
    ) = 1
    AND c.paid_amount > 0
""")

paid_no_other_charges = cur.fetchone()[0]
print(f"Charters with ONLY 'Unfilled Charge' and are paid: {paid_no_other_charges}")

# Check if these were originally zero charge
cur.execute("""
    SELECT COUNT(DISTINCT c.reserve_number)
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE cc.description = 'Unfilled Charge'
    AND cc.created_at = (SELECT MAX(created_at) FROM charter_charges WHERE charter_id = c.charter_id)
""")

just_added = cur.fetchone()[0]
print(f"Unfilled charges just added today (2026-01-23): {just_added}")

# Check a sample
print("\n" + "="*80)
print("SAMPLE UNFILLED CHARGES")
print("="*80)

cur.execute("""
    SELECT DISTINCT c.reserve_number, c.status, c.charter_date, c.total_amount_due, c.paid_amount,
           COALESCE(SUM(cc2.amount) FILTER (WHERE cc2.description != 'Unfilled Charge'), 0) as other_charges
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    LEFT JOIN charter_charges cc2 ON c.charter_id = cc2.charter_id AND cc2.description != 'Unfilled Charge'
    WHERE cc.description = 'Unfilled Charge'
    GROUP BY c.charter_id, c.reserve_number, c.status, c.charter_date, c.total_amount_due, c.paid_amount
    LIMIT 20
""")

print(f"\n{'Reserve':<10} {'Status':<15} {'Date':<12} {'Total Due':>12} {'Paid':>12} {'Other Charges':>15}")
print("-" * 80)

for row in cur.fetchall():
    print(f"{row[0]:<10} {(row[1] or 'NULL'):<15} {str(row[2]):<12} ${row[3]:>11.2f} ${row[4]:>11.2f} ${row[5]:>14.2f}")

cur.close()
conn.close()

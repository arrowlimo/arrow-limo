import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check the big "rounding" adjustments
cur.execute("""
    SELECT charge_id, charter_id, reserve_number, description, amount, created_at
    FROM charter_charges
    WHERE description = 'Rounding Adjustment'
    AND amount > 100
    ORDER BY amount DESC
    LIMIT 20
""")

rows = cur.fetchall()
print("Top 20 'Rounding Adjustments' over $100:\n")
print(f"{'ID':<8} {'Reserve':<10} {'Amount':>12} {'Created':<20}")
print("-" * 50)

for row in rows:
    print(f"{row[0]:<8} {row[2]:<10} ${row[4]:>11.2f} {str(row[5])[:10]}")

# Check charter 017822 specifically
print(f"\n\n{'='*70}")
print("CHARTER 017822 DETAILS")
print(f"{'='*70}\n")

cur.execute("""
    SELECT charter_id, reserve_number, status, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = '017822'
""")

charter = cur.fetchone()
if charter:
    print(f"Charter ID:          {charter[0]}")
    print(f"Reserve:             {charter[1]}")
    print(f"Status:              {charter[2]}")
    print(f"Date:                {charter[3]}")
    print(f"Total Due:           ${charter[4]:.2f}")
    print(f"Paid:                ${charter[5]:.2f}")
    print(f"Balance:             ${charter[6]:.2f}")
    
    # Get all charges
    cur.execute("""
        SELECT charge_id, description, amount, created_at
        FROM charter_charges
        WHERE reserve_number = '017822'
        ORDER BY created_at
    """)
    
    charges = cur.fetchall()
    print(f"\nCharges ({len(charges)} total):")
    print(f"{'ID':<8} {'Description':<30} {'Amount':>12} {'Date':<12}")
    print("-" * 65)
    
    total = 0
    for c in charges:
        print(f"{c[0]:<8} {(c[1] or '')[:30]:<30} ${c[2]:>11.2f} {str(c[3])[:10]}")
        total += c[2]
    
    print("-" * 65)
    print(f"{'TOTAL':<40} ${total:>11.2f}")
    
    if total == charter[4]:
        print(f"\n✅ Charges match total due")
    else:
        print(f"\n⚠️  Deficit/Overage: ${charter[4] - total:.2f}")

cur.close()
conn.close()

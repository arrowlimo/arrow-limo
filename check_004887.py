import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserve = "004887"

# Get charter
cur.execute("""
    SELECT charter_id, reserve_number, status, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = %s
""", (reserve,))

charter = cur.fetchone()

if charter:
    print(f"Charter {reserve}")
    print("="*70)
    print(f"Status: {charter[2]}")
    print(f"Date:   {charter[3]}")
    print(f"Total:  ${charter[4]:.2f}")
    print(f"Paid:   ${charter[5]:.2f}")
    print(f"Balance: ${charter[6]:.2f}\n")
    
    # Get all charges
    cur.execute("""
        SELECT charge_id, description, amount, created_at
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY created_at
    """, (reserve,))
    
    charges = cur.fetchall()
    
    print(f"ALL CHARGES ({len(charges)} total):")
    print(f"{'ID':<8} {'Description':<35} {'Amount':>12} {'Date':<12}")
    print("-" * 70)
    
    total = 0
    for c in charges:
        print(f"{c[0]:<8} {(c[1] or '')[:35]:<35} ${c[2]:>11.2f} {str(c[3])[:10]}")
        total += c[2]
    
    print("-" * 70)
    print(f"{'TOTAL':<45} ${total:>11.2f}")
    
    if abs(total - charter[4]) < 0.01:
        print(f"\n✅ Charges match total due")
    else:
        print(f"\n⚠️  Difference: ${charter[4] - total:.2f}")

cur.close()
conn.close()

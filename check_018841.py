import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check 018841
cur.execute("""
    SELECT charter_id, reserve_number, status, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = '018841'
""")
charter = cur.fetchone()

if charter:
    print(f"Charter ID: {charter[0]}, Reserve: {charter[1]}")
    print(f"Total: ${charter[4]:.2f}, Paid: ${charter[5]:.2f}\n")
    
    # All charges including NULL reserve
    cur.execute("""
        SELECT charge_id, reserve_number, charter_id, description, amount, created_at
        FROM charter_charges
        WHERE charter_id = %s OR reserve_number = %s
        ORDER BY created_at
    """, (charter[0], charter[1]))
    
    charges = cur.fetchall()
    print(f"All charges for this charter ({len(charges)} total):")
    print(f"{'ID':<8} {'Reserve':<12} {'Desc':<40} {'Amount':>12} {'Date':<12}")
    print("-" * 85)
    for c in charges:
        print(f"{c[0]:<8} {str(c[1] or 'NULL'):<12} {(c[3] or '')[:40]:<40} ${c[4]:>11.2f} {str(c[5])[:10]}")
    
    cur.execute("""
        SELECT SUM(amount) as total_charge_sum
        FROM charter_charges
        WHERE charter_id = %s OR reserve_number = %s
    """, (charter[0], charter[1]))
    
    total_sum = cur.fetchone()[0] or 0
    print(f"\nTotal charges sum: ${total_sum:.2f}")
    print(f"Total due:         ${charter[4]:.2f}")
    print(f"Deficit:           ${charter[4] - total_sum:.2f}")

cur.close()
conn.close()

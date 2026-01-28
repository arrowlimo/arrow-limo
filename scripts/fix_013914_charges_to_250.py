"""
Fix 013914 charges to match LMS ($250 total).
Current: $856.55 in 4 charges (incorrect import from 2025-07-24)
LMS shows: $250 total
"""
import psycopg2, os, sys

conn = psycopg2.connect(
    host='localhost', database='almsdata',
    user='postgres', password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("Fix Charter 013914 Charges to Match LMS")
print("="*80)
print()

reserve = '013914'

# Get charter_id
cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
charter_id = cur.fetchone()[0]

print(f"Charter ID: {charter_id}")
print(f"Reserve: {reserve}")
print()

# Current charges
print("Current Charges (INCORRECT):")
cur.execute("""
    SELECT charge_id, description, amount 
    FROM charter_charges 
    WHERE charter_id = %s
""", (charter_id,))
bad_charges = cur.fetchall()
for r in bad_charges:
    print(f"  ID {r[0]}: {r[1]} = ${r[2]:.2f}")
print(f"  Total: ${sum(r[2] for r in bad_charges):.2f}")
print()

print("LMS shows: $250.00 total")
print()

if '--apply' in sys.argv:
    print("APPLYING FIX...")
    
    # Backup
    cur.execute("""
        CREATE TABLE IF NOT EXISTS charter_charges_backup_013914_20251123 AS
        SELECT * FROM charter_charges WHERE charter_id = %s
    """, (charter_id,))
    print(f"✓ Created backup")
    
    # Delete incorrect charges
    cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (charter_id,))
    deleted = cur.rowcount
    print(f"✓ Deleted {deleted} incorrect charges")
    
    # Create correct charge
    cur.execute("""
        INSERT INTO charter_charges (charter_id, description, amount, created_at)
        VALUES (%s, 'Charter total (from LMS)', 250.00, CURRENT_TIMESTAMP)
    """, (charter_id,))
    print(f"✓ Created new charge: Charter total = $250.00")
    
    # Update charter totals
    cur.execute("""
        UPDATE charters
        SET total_amount_due = 250.00,
            balance = 250.00 - paid_amount
        WHERE charter_id = %s
    """, (charter_id,))
    print(f"✓ Updated charter total_amount_due to $250.00")
    
    conn.commit()
    
    # Verify
    cur.execute("""
        SELECT total_amount_due, paid_amount, balance 
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    due, paid, bal = cur.fetchone()
    print()
    print("✓ COMPLETE")
    print(f"  Total Due: ${due:.2f}")
    print(f"  Paid: ${paid:.2f}")
    print(f"  Balance: ${bal:.2f}")
    
    if abs(bal) < 0.01:
        print("\n✓✓ Charter 013914 is now BALANCED!")
else:
    print("DRY RUN - use --apply to fix")

cur.close()
conn.close()

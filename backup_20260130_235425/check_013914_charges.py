"""Check why 013914 shows $856.55 due instead of $250"""
import psycopg2, os

conn = psycopg2.connect(
    host='localhost', database='almsdata', 
    user='postgres', password='***REDACTED***'
)
cur = conn.cursor()

print("="*80)
print("Charter 013914 Charge Analysis")
print("="*80)

# Charter info
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, total_amount_due, 
           paid_amount, balance, rate, status, cancelled
    FROM charters WHERE reserve_number = '013914'
""")
row = cur.fetchone()
charter_id = row[0]
print(f"\nCharter ID: {charter_id}")
print(f"Reserve: {row[1]}")
print(f"Date: {row[2]}")
print(f"Total Due: ${row[3]:.2f}")
print(f"Paid: ${row[4]:.2f}")
print(f"Balance: ${row[5]:.2f}")
rate_str = f"${row[6]:.2f}" if row[6] else "$0.00"
print(f"Rate: {rate_str}")
print(f"Status: {row[7]}, Cancelled: {row[8]}")

# Charges
print("\nCharges in charter_charges:")
cur.execute("""
    SELECT charge_id, description, amount, created_at
    FROM charter_charges 
    WHERE charter_id = %s
    ORDER BY charge_id
""", (charter_id,))
charges = cur.fetchall()
if charges:
    for r in charges:
        print(f"  ID {r[0]}: {r[1]} = ${r[2]:.2f} (created {r[3]})")
    total = sum(r[2] for r in charges)
    print(f"\n  Sum of charges: ${total:.2f}")
else:
    print("  No charges found!")

print("\n" + "="*80)
print("ISSUE: total_amount_due ($856.55) doesn't match LMS ($250)")
print("="*80)
print("\nLMS shows Total Charge = $250.00")
print("Database shows total_amount_due = $856.55")
print("\nNeed to update total_amount_due to $250.00 to match LMS")

cur.close()
conn.close()

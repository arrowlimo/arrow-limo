import psycopg2
import os
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserve = "013886"

# Backup the charges before deleting
cur.execute("""
    SELECT charge_id, reserve_number, charter_id, description, amount, created_at
    FROM charter_charges
    WHERE reserve_number = %s
    ORDER BY charge_id
""", (reserve,))
charges = cur.fetchall()

backup_file = f"L:\\limo\\reports\\013886_charges_zeroed_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(backup_file, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['charge_id', 'reserve_number', 'charter_id', 'description', 'amount', 'created_at'])
    for row in charges:
        w.writerow(row)

# Delete the charges
cur.execute("DELETE FROM charter_charges WHERE reserve_number = %s", (reserve,))
conn.commit()

print(f"✅ Deleted {len(charges)} charges for charter {reserve}")
print(f"📁 Backup saved to: {backup_file}")

# Verify the fix
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.status, c.charter_date, c.total_amount_due, c.paid_amount, c.balance,
           COALESCE(SUM(ch.amount), 0) AS charge_sum
    FROM charters c
    LEFT JOIN charter_charges ch ON c.reserve_number = ch.reserve_number
    WHERE c.reserve_number = %s
    GROUP BY c.charter_id, c.reserve_number, c.status, c.charter_date, c.total_amount_due, c.paid_amount, c.balance
""", (reserve,))
result = cur.fetchone()

print(f"\n{'='*70}")
print(f"CHARTER {reserve} - AFTER ZEROING CHARGES")
print(f"{'='*70}")
print(f"Total Due:   ${result[4]:.2f}")
print(f"Paid:        ${result[5]:.2f}")
print(f"Charges:     ${result[7]:.2f}")
print(f"Balance:     ${result[6]:.2f}")
if result[4] == result[7]:
    print(f"\n✅ PARITY RESTORED: Charges now match total due!")
else:
    print(f"\n⚠️  Deficit: ${result[4] - result[7]:.2f}")

cur.close()
conn.close()

"""
Cancel a charter by reserve_number: remove charges, orphan payments, and zero totals.
Default dry-run; use --execute to apply changes.
Steps:
- Backup charges and payments to CSV under reports/.
- Delete charter_charges with this reserve_number.
- Set payments.reserve_number to NULL to orphan them (preserve payment record).
- Update charters: status='cancelled', total_amount_due=0, paid_amount=0, balance=0.
"""
import os
import sys
import csv
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

if len(sys.argv) < 2:
    print("Usage: python scripts/fix_cancelled_charter.py RESERVE_NUMBER [--execute]")
    sys.exit(1)

reserve = sys.argv[1]
EXECUTE = "--execute" in sys.argv
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print(f"Cancel charter {reserve} (dry-run={not EXECUTE})")

# Fetch charter
cur.execute("""
    SELECT charter_id, status, charter_date, total_amount_due, paid_amount, balance
    FROM charters WHERE reserve_number=%s
""", (reserve,))
row = cur.fetchone()
if not row:
    print("Charter not found")
    sys.exit(1)
charter_id, status, charter_date, total_amt, paid_amt, bal = row
print(f"Charter: id={charter_id}, status={status or 'NULL'}, date={charter_date}, total={total_amt}, paid={paid_amt}, balance={bal}")

# Charges
cur.execute("""
    SELECT charge_id, amount, description, charge_type, account_number
    FROM charter_charges WHERE reserve_number=%s
    ORDER BY charge_id
""", (reserve,))
charges = cur.fetchall()
charge_sum = sum([c[1] for c in charges]) if charges else 0
print(f"Charges: {len(charges)} rows, sum={charge_sum}")

# Payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_method
    FROM payments WHERE reserve_number=%s
    ORDER BY payment_id
""", (reserve,))
payments = cur.fetchall()
pay_sum = sum([p[1] for p in payments]) if payments else 0
print(f"Payments: {len(payments)} rows, sum={pay_sum}")

# Backup files
os.makedirs("reports", exist_ok=True)
charges_csv = f"reports/{reserve}_charges_backup_{stamp}.csv"
payments_csv = f"reports/{reserve}_payments_backup_{stamp}.csv"

with open(charges_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["charge_id", "amount", "description", "charge_type", "account_number"])
    w.writerows(charges)
with open(payments_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["payment_id", "amount", "payment_date", "payment_method"])
    w.writerows(payments)
print(f"Backups written: {charges_csv}, {payments_csv}")

if EXECUTE:
    try:
        # Delete charges
        cur.execute("DELETE FROM charter_charges WHERE reserve_number=%s", (reserve,))
        print(f"Deleted charges: {cur.rowcount}")
        # Orphan payments
        cur.execute("UPDATE payments SET reserve_number=NULL WHERE reserve_number=%s", (reserve,))
        print(f"Orphaned payments: {cur.rowcount}")
        # Update charter totals/status
        cur.execute("""
            UPDATE charters
            SET status='cancelled', total_amount_due=0, paid_amount=0, balance=0
            WHERE reserve_number=%s
        """, (reserve,))
        print(f"Updated charter row: {cur.rowcount}")
        conn.commit()
        print("Committed.")
    except Exception as e:
        conn.rollback()
        print("Rolled back due to error:", e)
else:
    print("Dry-run only. Re-run with --execute to apply changes.")

cur.close()
conn.close()

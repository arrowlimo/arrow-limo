"""
Reconcile charter_charges with NULL/empty reserve_number:
- Update: for rows with charter_id linking to a non-cancelled charter and NOT an LMS total artifact,
         set reserve_number to the charter's reserve_number.
- Delete: rows that are LMS total artifacts (description starts with 'Charter total (from LMS Est_Charge)')
         regardless of status, and rows with BOTH NULL reserve_number AND NULL charter_id.

Safety:
- Dry-run by default. Use --execute to apply changes.
- CSV backups for to-be-deleted and to-be-updated rows.
- Uses reserve_number (business key) when writing.
"""
import os
import sys
import csv
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

EXECUTE = "--execute" in sys.argv
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 88)
print("Reconcile NULL-reserve charter_charges (dry-run=" + str(not EXECUTE) + ")")
print("=" * 88)

# 1) Summarize population
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount),0)
    FROM charter_charges
    WHERE reserve_number IS NULL OR reserve_number = ''
""")
count_all, sum_all = cur.fetchone()
print(f"Target population: {count_all:,d} charges totaling ${sum_all:,.2f}")

# 2) Identify LMS total artifacts to delete
cur.execute("""
    WITH base AS (
        SELECT cc.charge_id, cc.charter_id, cc.description, cc.amount, cc.charge_type
        FROM charter_charges cc
        WHERE cc.reserve_number IS NULL OR cc.reserve_number = ''
    )
    SELECT COUNT(*), COALESCE(SUM(amount),0)
    FROM base
    WHERE description ILIKE 'Charter total (from LMS Est_Charge)%'
""")
count_artifacts, sum_artifacts = cur.fetchone()
print(f"LMS total artifacts (to delete): {count_artifacts:,d} charges totaling ${sum_artifacts:,.2f}")

# 3) Identify fully orphaned rows (no charter_id)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount),0)
    FROM charter_charges
    WHERE (reserve_number IS NULL OR reserve_number = '') AND charter_id IS NULL
""")
count_orphans, sum_orphans = cur.fetchone()
print(f"Fully orphaned (NULL charter_id) (to delete): {count_orphans:,d} charges totaling ${sum_orphans:,.2f}")

# 4) Identify update candidates: real line items linked to a charter
cur.execute("""
    WITH linked AS (
        SELECT cc.charge_id, cc.charter_id, cc.description, cc.amount, cc.charge_type, c.reserve_number, c.status
        FROM charter_charges cc
        JOIN charters c ON cc.charter_id = c.charter_id
        WHERE (cc.reserve_number IS NULL OR cc.reserve_number = '')
    )
    SELECT COUNT(*), COALESCE(SUM(amount),0)
    FROM linked
    WHERE description NOT ILIKE 'Charter total (from LMS Est_Charge)%'
""")
count_updates, sum_updates = cur.fetchone()
print(f"Line items to link (set reserve_number): {count_updates:,d} charges totaling ${sum_updates:,.2f}")

# 5) Preview samples
print("\nSample update candidates:")
cur.execute("""
    SELECT cc.charge_id, c.reserve_number, c.status, cc.description, cc.amount, cc.charge_type
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE (cc.reserve_number IS NULL OR cc.reserve_number = '')
      AND cc.description NOT ILIKE 'Charter total (from LMS Est_Charge)%'
    ORDER BY cc.amount DESC
    LIMIT 10
""")
for row in cur.fetchall():
    charge_id, reserve_number, status, description, amount, charge_type = row
    desc_short = (description[:60] + '...') if description and len(description) > 60 else (description or 'NULL')
    print(f"  #{charge_id} | {reserve_number} | {status or 'NULL'} | ${amount:,.2f} | {charge_type or 'NULL'} | {desc_short}")

print("\nSample delete artifacts:")
cur.execute("""
    SELECT cc.charge_id, cc.charter_id, cc.description, cc.amount, cc.charge_type
    FROM charter_charges cc
    WHERE (cc.reserve_number IS NULL OR cc.reserve_number = '')
      AND cc.description ILIKE 'Charter total (from LMS Est_Charge)%'
    ORDER BY cc.amount DESC
    LIMIT 10
""")
for row in cur.fetchall():
    charge_id, charter_id, description, amount, charge_type = row
    desc_short = (description[:60] + '...') if description and len(description) > 60 else (description or 'NULL')
    print(f"  #{charge_id} | charter_id={charter_id or 'NULL'} | ${amount:,.2f} | {charge_type or 'NULL'} | {desc_short}")

# Backups
updates_csv = f"reports/charter_charges_updates_{TIMESTAMP}.csv"
deletes_csv = f"reports/charter_charges_deletes_{TIMESTAMP}.csv"

# Prepare data for backups
cur.execute("""
    SELECT cc.charge_id, cc.charter_id, c.reserve_number AS new_reserve_number,
           cc.description, cc.amount, cc.charge_type
    FROM charter_charges cc
    JOIN charters c ON cc.charter_id = c.charter_id
    WHERE (cc.reserve_number IS NULL OR cc.reserve_number = '')
      AND cc.description NOT ILIKE 'Charter total (from LMS Est_Charge)%'
""")
update_rows = cur.fetchall()

cur.execute("""
    SELECT cc.charge_id, cc.charter_id, cc.description, cc.amount, cc.charge_type
    FROM charter_charges cc
    WHERE (cc.reserve_number IS NULL OR cc.reserve_number = '')
      AND (
        cc.description ILIKE 'Charter total (from LMS Est_Charge)%'
        OR cc.charter_id IS NULL
      )
""")
delete_rows = cur.fetchall()

# Write backups (always)
os.makedirs("reports", exist_ok=True)
with open(updates_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["charge_id", "charter_id", "new_reserve_number", "description", "amount", "charge_type"]) 
    w.writerows(update_rows)

with open(deletes_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["charge_id", "charter_id", "description", "amount", "charge_type"]) 
    w.writerows(delete_rows)

print(f"\nBackups written:\n  Updates -> {updates_csv}\n  Deletes -> {deletes_csv}")

if EXECUTE:
    try:
        # Apply updates using reserve_number (business key)
        print("\nApplying updates (setting reserve_number on real line items)...")
        cur.execute("""
            UPDATE charter_charges cc
            SET reserve_number = c.reserve_number
            FROM charters c
            WHERE cc.charter_id = c.charter_id
              AND (cc.reserve_number IS NULL OR cc.reserve_number = '')
              AND cc.description NOT ILIKE 'Charter total (from LMS Est_Charge)%'
        """)
        print(f"  Updated rows: {cur.rowcount:,d}")

        # Apply deletes for artifacts and fully orphaned rows
        print("Deleting LMS total artifacts and fully orphaned rows...")
        cur.execute("""
            DELETE FROM charter_charges cc
            WHERE (cc.reserve_number IS NULL OR cc.reserve_number = '')
              AND (
                cc.description ILIKE 'Charter total (from LMS Est_Charge)%'
                OR cc.charter_id IS NULL
              )
        """)
        print(f"  Deleted rows: {cur.rowcount:,d}")

        conn.commit()
        print("\nCommitted changes.")
    except Exception as e:
        conn.rollback()
        print(f"\nRolled back due to error: {e}")
else:
    print("\nDry-run only. Re-run with --execute to apply changes.")

cur.close()
conn.close()

print("\n" + "=" * 88)
print("Reconciliation complete")
print("=" * 88)

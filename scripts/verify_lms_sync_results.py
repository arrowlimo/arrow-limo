"""
Check the results of the LMS sync to see what was updated.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 120)
print("LMS SYNC RESULTS VERIFICATION")
print("=" * 120)
print()

# Check sync log
print("Recent LMS Sync Operations:")
print("-" * 120)
cur.execute("""
    SELECT sync_id, sync_timestamp, records_processed, records_updated, 
           records_inserted, sync_type, notes
    FROM lms_sync_log
    ORDER BY sync_timestamp DESC
    LIMIT 5
""")

for row in cur.fetchall():
    sync_id, timestamp, processed, updated, inserted, sync_type, notes = row
    print(f"Sync {sync_id}: {timestamp}")
    print(f"  Type: {sync_type}")
    print(f"  Processed: {processed}, Updated: {updated}, Inserted: {inserted}")
    print(f"  Notes: {notes}")
    print()

# Check newly inserted charters
print("\n" + "=" * 120)
print("NEWLY SYNCED CHARTERS (from latest sync)")
print("=" * 120)

cur.execute("""
    SELECT charter_id, reserve_number, charter_date, rate, balance, notes
    FROM charters
    WHERE created_at > (
        SELECT MAX(sync_timestamp) - INTERVAL '1 hour'
        FROM lms_sync_log
    )
    ORDER BY charter_id DESC
    LIMIT 10
""")

for row in cur.fetchall():
    cid, reserve, cdate, rate, balance, notes = row
    print(f"Charter {cid}: Reserve {reserve}, Date {cdate}")
    print(f"  Rate: ${rate if rate else 0:.2f}, Balance: ${balance if balance else 0:.2f}")
    print(f"  Notes: {notes[:80] if notes else 'NULL'}")
    print()

# Check newly inserted payments
print("\n" + "=" * 120)
print("NEWLY SYNCED PAYMENTS (from latest sync)")
print("=" * 120)

cur.execute("""
    SELECT p.payment_id, p.payment_date, p.amount, p.charter_id, p.reserve_number, 
           p.account_number, c.reserve_number as charter_reserve
    FROM payments p
    LEFT JOIN charters c ON p.charter_id = c.charter_id
    WHERE p.created_at > (
        SELECT MAX(sync_timestamp) - INTERVAL '1 hour'
        FROM lms_sync_log
    )
    ORDER BY p.payment_id DESC
    LIMIT 15
""")

payments_synced = cur.fetchall()
for row in payments_synced:
    pid, pdate, amount, charter_id, reserve, account, charter_reserve = row
    match_status = "[OK] MATCHED" if charter_id else "[WARN] UNMATCHED"
    print(f"Payment {pid}: ${amount if amount else 0:.2f} on {pdate} - {match_status}")
    print(f"  Charter ID: {charter_id if charter_id else 'NULL'}, "
          f"Reserve: {reserve if reserve else 'NULL'} → Charter: {charter_reserve if charter_reserve else 'NULL'}")
    print(f"  Account: {account if account else 'NULL'}")
    print()

# Check matching statistics after sync
print("\n" + "=" * 120)
print("UPDATED MATCHING STATISTICS")
print("=" * 120)

cur.execute("""
    SELECT 
        COUNT(*) as total_payments,
        COUNT(charter_id) as matched_payments,
        COUNT(*) - COUNT(charter_id) as unmatched_payments,
        ROUND(100.0 * COUNT(charter_id) / COUNT(*), 2) as match_percentage
    FROM payments
    WHERE payment_date >= '2007-01-01' AND payment_date < '2025-01-01'
""")

stats = cur.fetchone()
total, matched, unmatched, pct = stats
print(f"Total payments (2007-2024):     {total:,}")
print(f"Matched:                        {matched:,} ({pct}%)")
print(f"Unmatched:                      {unmatched:,} ({100-pct:.2f}%)")
print()

# Check if any previously unmatched payments got matched
print("Checking if sync helped match previously unmatched payments...")

cur.execute("""
    SELECT COUNT(*)
    FROM payments
    WHERE reserve_number IS NOT NULL
      AND updated_at > (
          SELECT MAX(sync_timestamp) - INTERVAL '1 hour'
          FROM lms_sync_log
      )
      AND created_at < (
          SELECT MAX(sync_timestamp) - INTERVAL '1 day'
          FROM lms_sync_log
      )
""")

newly_matched = cur.fetchone()[0]
if newly_matched > 0:
    print(f"[OK] {newly_matched} previously unmatched payments now matched!")
else:
    print("No previously unmatched payments were matched by this sync")

cur.close()
conn.close()

"""
Check if orphaned_charges_archive and lms_staging_customer_archived are still needed.

1. orphaned_charges_archive: Are these still orphaned or reconciled to charters?
2. lms_staging_customer_archived: Is this data already in clients table?
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 80)
print("ORPHANED CHARGES ARCHIVE CHECK")
print("=" * 80)

# Check orphaned_charges_archive structure and sample data
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'orphaned_charges_archive'
    ORDER BY ordinal_position
""")
print("\norphaned_charges_archive columns:")
for col, dtype in cur.fetchall():
    print(f"  {col:30} {dtype}")

cur.execute("SELECT COUNT(*) FROM orphaned_charges_archive")
orphaned_count = cur.fetchone()[0]
print(f"\nTotal archived orphaned charges: {orphaned_count:,}")

# Check if reserve_numbers in orphaned_charges_archive now exist in charters
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN c.reserve_number IS NOT NULL THEN 1 END) as now_exists,
        COUNT(CASE WHEN c.reserve_number IS NULL THEN 1 END) as still_orphaned
    FROM orphaned_charges_archive oca
    LEFT JOIN charters c ON c.reserve_number = oca.reserve_number
""")
result = cur.fetchone()
total, now_exists, still_orphaned = result

print(f"\nReconciliation status:")
print(f"  Total charges in archive: {total:,}")
print(f"  Now linked to charters: {now_exists:,} ({100*now_exists/total:.1f}%)")
print(f"  Still orphaned: {still_orphaned:,} ({100*still_orphaned/total:.1f}%)")

if now_exists > 0:
    print(f"\n✅ {now_exists:,} charges have been reconciled - archive can be dropped")
if still_orphaned > 0:
    print(f"\n⚠️ {still_orphaned:,} charges remain orphaned")
    # Sample of still orphaned
    cur.execute("""
        SELECT oca.reserve_number, oca.total_amount, oca.charge_count
        FROM orphaned_charges_archive oca
        LEFT JOIN charters c ON c.reserve_number = oca.reserve_number
        WHERE c.reserve_number IS NULL
        LIMIT 5
    """)
    samples = cur.fetchall()
    if samples:
        print("\nSample of still orphaned:")
        for reserve, amt, count in samples:
            print(f"  {reserve}: {count} charges totaling ${amt}")

print("\n" + "=" * 80)
print("LMS STAGING CUSTOMER ARCHIVED CHECK")
print("=" * 80)

# Check lms_staging_customer_archived structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'lms_staging_customer_archived_20251109'
    ORDER BY ordinal_position
""")
print("\nlms_staging_customer_archived_20251109 columns:")
for col, dtype in cur.fetchall():
    print(f"  {col:30} {dtype}")

cur.execute("SELECT COUNT(*) FROM lms_staging_customer_archived_20251109")
staging_count = cur.fetchone()[0]
print(f"\nTotal archived staging customers: {staging_count:,}")

# Check if these customers exist in clients table by customer_id
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN c.client_id IS NOT NULL THEN 1 END) as in_clients,
        COUNT(CASE WHEN c.client_id IS NULL THEN 1 END) as not_in_clients
    FROM lms_staging_customer_archived_20251109 lsc
    LEFT JOIN clients c ON c.client_id = lsc.customer_id
""")
result = cur.fetchone()
total, in_clients, not_in_clients = result

print(f"\nClients table match (by customer_id):")
print(f"  Total staging customers: {total:,}")
print(f"  Found in clients: {in_clients:,} ({100*in_clients/total:.1f}%)")
print(f"  Not in clients: {not_in_clients:,} ({100*not_in_clients/total:.1f}%)")

if in_clients == total:
    print(f"\n✅ All staging customers exist in clients table - archive can be dropped")
elif not_in_clients > 0:
    print(f"\n⚠️ {not_in_clients:,} customers not in clients table")

print("\n" + "=" * 80)
print("VERDICT")
print("=" * 80)
print("\nRecommendation:")
if now_exists == total and in_clients == staging_count:
    print("  ✅ DROP BOTH - All data reconciled to production tables")
elif now_exists == total:
    print("  ✅ DROP orphaned_charges_archive - All charges reconciled")
elif in_clients == staging_count:
    print("  ✅ DROP lms_staging_customer_archived - All customers in clients")
else:
    print("  ⚠️ REVIEW - Some data may not be reconciled")

cur.close()
conn.close()

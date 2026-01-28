"""
Delete CIBC 8362 2014-2017 import to prepare for corrected re-upload
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 100)
print("DELETE CIBC 8362 (2014-2017) IMPORT - Prepare for corrected re-upload")
print("=" * 100)

# Check what will be deleted
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE bank_id = 1
    AND source_file = '2014-2017 CIBC 8362.xlsx'
""")

count, min_date, max_date = cur.fetchone()

print(f"\n📊 Records to delete: {count:,}")
print(f"   Date range: {min_date} to {max_date}")
print(f"   Source: 2014-2017 CIBC 8362.xlsx")

if count == 0:
    print("\n✅ No records to delete")
    cur.close()
    conn.close()
    exit(0)

response = input(f"\nDelete {count:,} records? (YES to proceed): ")

if response != "YES":
    print("❌ Cancelled")
    cur.close()
    conn.close()
    exit(0)

# Delete
print("\n🗑️ Deleting...")

cur.execute("""
    DELETE FROM banking_transactions
    WHERE bank_id = 1
    AND source_file = '2014-2017 CIBC 8362.xlsx'
""")

deleted = cur.rowcount

# Commit
conn.commit()
print(f"\n✅ COMMITTED - Deleted {deleted:,} records")

# Verify
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE bank_id = 1
    AND source_file = '2014-2017 CIBC 8362.xlsx'
""")

remaining = cur.fetchone()[0]

if remaining == 0:
    print("✅ All records removed - ready for corrected re-upload")
else:
    print(f"⚠️ Warning: {remaining} records still remain")

cur.close()
conn.close()

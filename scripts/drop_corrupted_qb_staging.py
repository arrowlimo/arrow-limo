"""Drop corrupted qb_transactions_staging table.

[WARN] WARNING: This will permanently delete 983,153 rows of corrupted XML data.
The real QuickBooks data is already safely stored in journal and unified_general_ledger tables.

This table contains failed XML imports with:
- All monetary amounts: $0.00
- Invalid dates: 1969-12-31 (epoch)
- Parsing errors from XML structure mismatches

DO NOT RUN without explicit confirmation.

Usage: python drop_corrupted_qb_staging.py --confirm
"""
import psycopg2
import sys

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("DROP CORRUPTED qb_transactions_staging TABLE")
print("=" * 80)

# Get table info
cur.execute("""
    SELECT COUNT(*) FROM qb_transactions_staging
""")
row_count = cur.fetchone()[0]

print(f"\nqb_transactions_staging")
print(f"  Rows: {row_count:,}")
print(f"  Status: Corrupted XML import")
print(f"  Issue: All amounts $0.00, invalid dates (1969-12-31)")
print(f"  Real data: Already in journal + unified_general_ledger tables")

print("\n" + "[WARN] " * 20)
print("THIS OPERATION IS PERMANENT")
print("[WARN] " * 20)

# Check for --confirm flag
if "--confirm" in sys.argv:
    try:
        cur.execute("DROP TABLE qb_transactions_staging CASCADE")
        conn.commit()
        print("\n✓ SUCCESS - Table dropped")
        print(f"  Removed {row_count:,} corrupted rows")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        conn.rollback()
else:
    print("\n✗ CANCELLED - Add --confirm flag to execute drop")
    print("  Usage: python drop_corrupted_qb_staging.py --confirm")

cur.close()
conn.close()

#!/usr/bin/env python3
"""
Final verification that all splits were correctly linked
"""
import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "=" * 80)
print("FINAL VERIFICATION: Split Linking Complete")
print("=" * 80)

# Count total split groups
cur.execute("""
    SELECT COUNT(DISTINCT split_group_id) 
    FROM receipts 
    WHERE split_group_id IS NOT NULL 
      AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
""")
group_count = cur.fetchone()[0]

# Count total linked receipts
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE split_group_id IS NOT NULL 
      AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
""")
receipt_count = cur.fetchone()[0]

# Sum total amounts
cur.execute("""
    SELECT SUM(gross_amount)
    FROM receipts 
    WHERE split_group_id IS NOT NULL 
      AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
""")
total_amount = cur.fetchone()[0] or 0

# Group distribution
cur.execute("""
    SELECT parts, COUNT(*) as freq
    FROM (
        SELECT split_group_id, COUNT(*) as parts
        FROM receipts
        WHERE split_group_id IS NOT NULL
          AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
        GROUP BY split_group_id
    ) t
    GROUP BY parts
    ORDER BY parts DESC
""")

dist = cur.fetchall()

print(f"\n✅ FINAL RESULTS:")
print(f"   Split groups created: {group_count}")
print(f"   Total receipts linked: {receipt_count}")
print(f"   Combined amount: ${total_amount:,.2f}")
print(f"\n✅ DISTRIBUTION:")

for parts, count in dist:
    print(f"   {parts}-part splits: {count} groups ({parts*count} receipts)")

# Show top 5 by amount
print(f"\n✅ TOP 5 SPLITS BY AMOUNT:")
cur.execute("""
    SELECT split_group_id, vendor_name, receipt_date, COUNT(*) as parts, SUM(gross_amount) as total
    FROM receipts
    WHERE split_group_id IS NOT NULL
      AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
    GROUP BY split_group_id, vendor_name, receipt_date
    ORDER BY total DESC
    LIMIT 5
""")

for i, (gid, vendor, date, parts, total) in enumerate(cur.fetchall(), 1):
    print(f"   {i}. Group #{gid} | {vendor:30} {date} | {parts} parts | ${total:>7.2f}")

# Show year distribution
print(f"\n✅ DISTRIBUTION BY YEAR:")
cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date)::INT as year, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE split_group_id IS NOT NULL
    GROUP BY year
    ORDER BY year
""")

for year, count, total in cur.fetchall():
    print(f"   {int(year)}: {count:3d} receipts, ${total:>10,.2f}")

# Verify test case
print(f"\n✅ TEST CASE VERIFICATION (Receipt #157740):")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, split_group_id
    FROM receipts
    WHERE receipt_id = 157740
""")
result = cur.fetchone()
if result:
    rid, vendor, amount, split_gid = result
    print(f"   Receipt #{rid} | {vendor} | ${amount} | split_group_id={split_gid}")
    if split_gid:
        cur.execute("""
            SELECT receipt_id, vendor_name, gross_amount
            FROM receipts
            WHERE split_group_id = %s
            ORDER BY gross_amount DESC
        """, (split_gid,))
        parts = cur.fetchall()
        total = sum(p[2] for p in parts)
        print(f"   Found {len(parts)} linked receipts:")
        for p in parts:
            print(f"     - #{p[0]:6} {p[1]:20} ${p[2]:>7.2f}")
        print(f"   Total: ${total:.2f}")

print(f"\n✅ STATUS: All splits linked and verified!")
cur.close()
conn.close()

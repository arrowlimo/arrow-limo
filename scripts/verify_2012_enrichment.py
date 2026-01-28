import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Check enrichment results
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN vendor_extracted IS NOT NULL AND vendor_extracted != '' THEN 1 END) as with_vendor,
        COUNT(CASE WHEN description LIKE '%[QB:%' THEN 1 END) as with_qb_memo
    FROM banking_transactions 
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
""")

row = cur.fetchone()
total, with_vendor, with_memo = row

print("2012 Banking Transaction Enrichment Results:")
print("=" * 60)
print(f"Total transactions: {total:,}")
print(f"With vendor names: {with_vendor:,} ({with_vendor/total*100:.1f}%)")
print(f"With QB memos: {with_memo:,} ({with_memo/total*100:.1f}%)")
print()

# Sample enriched transactions
cur.execute("""
    SELECT transaction_date, vendor_extracted, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    ORDER BY transaction_date
    LIMIT 10
""")

print("Sample enriched transactions:")
print("-" * 60)
for row in cur.fetchall():
    date, vendor, desc = row
    print(f"{date} | {vendor:20s} | {desc[:40]}")

cur.close()
conn.close()

"""
Show remaining GL categorization gaps - vendors with unknown/uncategorized GL codes.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Count receipts by GL categorization status
print("=== GL CATEGORIZATION STATUS ===\n")

# Receipts with proper GL codes
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE gl_account_code IS NOT NULL 
    AND gl_account_code NOT IN ('6900', '')
    AND receipt_date >= '2012-01-01'
""")
proper_count, proper_total = cur.fetchone()
print(f"✅ Receipts with proper GL codes: {proper_count:,} (${proper_total:,.2f})")

# Receipts with GL 6900 (Unknown)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE gl_account_code = '6900'
    AND receipt_date >= '2012-01-01'
""")
unknown_count, unknown_total = cur.fetchone()
print(f"❓ GL 6900 (Unknown): {unknown_count:,} (${unknown_total:,.2f})")

# Receipts with no GL code
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE gl_account_code IS NULL OR gl_account_code = ''
    AND receipt_date >= '2012-01-01'
""")
null_count, null_total = cur.fetchone()
print(f"❌ No GL code: {null_count:,} (${null_total:,.2f})")

total_count = proper_count + unknown_count + null_count
total_amount = proper_total + unknown_total + null_total
print(f"\nTotal receipts: {total_count:,} (${total_amount:,.2f})")

# Top 30 vendors needing GL categorization
print("\n\n=== TOP 30 VENDORS NEEDING GL CATEGORIZATION ===\n")

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        COALESCE(SUM(gross_amount), 0) as total,
        STRING_AGG(DISTINCT COALESCE(gl_account_code, 'NULL'), ', ' ORDER BY COALESCE(gl_account_code, 'NULL')) as gl_codes
    FROM receipts
    WHERE (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    AND receipt_date >= '2012-01-01'
    GROUP BY vendor_name
    ORDER BY total DESC
    LIMIT 30
""")

print(f"{'Vendor':<50} {'Count':>7} {'Total':>14} {'GL Codes'}")
print("-" * 100)

for vendor, count, total, gl_codes in cur.fetchall():
    vendor_display = vendor[:47] + '...' if len(vendor) > 50 else vendor
    print(f"{vendor_display:<50} {count:>7} {total:>13,.0f} {gl_codes}")

cur.close()
conn.close()

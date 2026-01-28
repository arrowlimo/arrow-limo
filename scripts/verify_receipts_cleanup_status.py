"""
Verify receipts table cleanup and deduplication status
Check for duplicates, cleaned vendor names, and data quality
"""
import psycopg2
import os

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== RECEIPTS TABLE STATUS ===\n")

# 1. Total receipts count
cur.execute("SELECT COUNT(*) FROM receipts")
total = cur.fetchone()[0]
print(f"Total receipts: {total:,}")

# 2. Check for duplicate patterns (same date + vendor + amount)
cur.execute("""
    SELECT 
        COUNT(*) as duplicate_groups,
        SUM(count) as total_duplicates
    FROM (
        SELECT COUNT(*) as count
        FROM receipts
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
    ) subq
""")
dup_result = cur.fetchone()
print(f"\nDuplicate analysis:")
print(f"  - Duplicate groups (same date+vendor+amount): {dup_result[0] or 0:,}")
print(f"  - Total receipts in duplicate groups: {dup_result[1] or 0:,}")

# 3. Check for vendor name artifacts (suffixes, location codes, etc.)
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE vendor_name LIKE '%RED D%') as red_d,
        COUNT(*) FILTER (WHERE vendor_name LIKE '%Liquor Barn%Store%') as liquor_location,
        COUNT(*) FILTER (WHERE vendor_name LIKE '%DRYDE%') as dryde,
        COUNT(*) FILTER (WHERE vendor_name LIKE '%2012-05-15%') as garbled_date,
        COUNT(*) FILTER (WHERE vendor_name ~ '[#@$%^&*]{3,}') as special_chars
    FROM receipts
""")
artifacts = cur.fetchone()
print(f"\nVendor name artifacts:")
print(f"  - 'RED D' suffixes: {artifacts[0]}")
print(f"  - Liquor Barn location codes: {artifacts[1]}")
print(f"  - 'DRYDE' issues: {artifacts[2]}")
print(f"  - Garbled dates (2012-05-15): {artifacts[3]}")
print(f"  - Special character clusters: {artifacts[4]}")
total_artifacts = sum(artifacts)
print(f"  TOTAL ARTIFACTS: {total_artifacts}")

# 4. Check for recurring payment patterns (protected from deduplication)
cur.execute("""
    SELECT 
        COUNT(*) as recurring_count
    FROM receipts
    WHERE vendor_name ~* '(RENT|LEASE|INSURANCE|MORTGAGE|UTILITIES|PHONE|INTERNET|SUBSCRIPTION)'
""")
recurring = cur.fetchone()[0]
print(f"\nRecurring payments (protected): {recurring:,}")

# 5. Check for NSF patterns
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE description ~* 'NSF') as nsf_receipts,
        COUNT(*) FILTER (WHERE description ~* 'Customer Payment.*NSF') as nsf_reversals
    FROM receipts
""")
nsf = cur.fetchone()
print(f"\nNSF patterns:")
print(f"  - NSF charges: {nsf[0]:,}")
print(f"  - NSF reversals: {nsf[1]:,}")

# 6. Sample potential duplicates (if any exist)
cur.execute("""
    SELECT 
        receipt_date,
        vendor_name,
        gross_amount,
        COUNT(*) as count
    FROM receipts
    GROUP BY receipt_date, vendor_name, gross_amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, gross_amount DESC
    LIMIT 10
""")
sample_dups = cur.fetchall()

if sample_dups:
    print(f"\n\n=== TOP 10 POTENTIAL DUPLICATE PATTERNS ===")
    print("-" * 80)
    for row in sample_dups:
        print(f"{row[0]} | {row[1][:40]:<40} | ${row[2]:>10.2f} | Count: {row[3]}")
    
    print("\nNOTE: These may be legitimate recurring payments (rent, lease, insurance)")
else:
    print(f"\n✓ NO DUPLICATES FOUND")

# 7. Check deduplication history/backups
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%receipt%backup%'
    ORDER BY table_name
""")
backups = cur.fetchall()
print(f"\n\n=== BACKUP TABLES ===")
if backups:
    for backup in backups:
        cur.execute(f"SELECT COUNT(*) FROM {backup[0]}")
        count = cur.fetchone()[0]
        print(f"  - {backup[0]}: {count:,} rows")
else:
    print("  No backup tables found")

# 8. Check color coding system
cur.execute("""
    SELECT 
        display_color,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
    FROM receipts
    WHERE display_color IS NOT NULL
    GROUP BY display_color
    ORDER BY count DESC
""")
colors = cur.fetchall()
print(f"\n\n=== COLOR CODING STATUS ===")
if colors:
    for row in colors:
        print(f"  {row[0]:10} | {row[1]:>7,} receipts ({row[2]:>5.1f}%)")
else:
    print("  No color coding found")

# 9. Banking reconciliation status
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as matched,
        COUNT(*) FILTER (WHERE banking_transaction_id IS NULL) as unmatched,
        COUNT(*) as total
    FROM receipts
""")
banking = cur.fetchone()
matched_pct = (banking[0] / banking[2] * 100) if banking[2] > 0 else 0
print(f"\n\n=== BANKING RECONCILIATION ===")
print(f"  Matched to banking: {banking[0]:,} ({matched_pct:.1f}%)")
print(f"  Unmatched: {banking[1]:,}")

# 10. Final summary
cur.execute("""
    SELECT 
        COUNT(*) as total,
        MIN(receipt_date) as earliest,
        MAX(receipt_date) as latest,
        SUM(gross_amount) as total_amount
    FROM receipts
""")
summary = cur.fetchone()

print(f"\n\n=== FINAL SUMMARY ===")
print(f"Total receipts: {summary[0]:,}")
print(f"Date range: {summary[1]} to {summary[2]}")
print(f"Total amount: ${summary[3]:,.2f}")
print(f"\n✓ Vendor artifacts: {total_artifacts} (should be 0 if cleaned)")
print(f"✓ Duplicate groups: {dup_result[0] or 0} (smart deduplication protects recurring)")
print(f"✓ Banking matched: {matched_pct:.1f}%")
print(f"✓ Color coded: {len(colors) > 0}")

cur.close()
conn.close()

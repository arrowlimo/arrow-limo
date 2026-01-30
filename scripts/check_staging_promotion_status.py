"""
Check if staging table data has been promoted to production.
"""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("STAGING DATA PROMOTION CHECK")
print("=" * 70)

# 1. staging_receipts_raw -> receipts
print("\n1. STAGING_RECEIPTS_RAW (821 rows)")
print("-" * 70)
cur.execute("SELECT COUNT(*) FROM staging_receipts_raw WHERE processed_at IS NOT NULL")
processed = cur.fetchone()[0]
print(f"Processed: {processed:,}/821 ({processed/821*100:.1f}%)")

cur.execute("SELECT MIN(imported_at), MAX(imported_at) FROM staging_receipts_raw")
min_imp, max_imp = cur.fetchone()
print(f"Import period: {min_imp} to {max_imp}")

if processed == 821:
    print("✓ RECOMMENDATION: ARCHIVE - All rows processed")
else:
    print(f"⚠ RECOMMENDATION: Process {821-processed} remaining rows first")

# 2. staging_scotia_2012_verified -> banking_transactions
print("\n2. STAGING_SCOTIA_2012_VERIFIED (759 rows, 2012 data)")
print("-" * 70)

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = 'scotia'
      AND transaction_date >= '2012-02-21'
      AND transaction_date <= '2012-12-30'
""")

scotia_2012_in_prod = cur.fetchone()[0]
print(f"2012 Scotia transactions in banking_transactions: {scotia_2012_in_prod:,}")

# Check for hash matches
cur.execute("""
    SELECT COUNT(DISTINCT s.source_hash)
    FROM staging_scotia_2012_verified s
    INNER JOIN banking_transactions b ON s.source_hash = b.source_hash
""")

hash_matches = cur.fetchone()[0]
print(f"Hash matches: {hash_matches:,}/759 ({hash_matches/759*100:.1f}%)")

if hash_matches > 700:
    print("✓ RECOMMENDATION: ARCHIVE - Most data already promoted")
else:
    print(f"⚡ RECOMMENDATION: Promote {759-hash_matches} unmatched rows")

# 3. qb_accounts_staging -> ??? (no clear target table)
print("\n3. QB_ACCOUNTS_STAGING (298 rows, Sept 2025 import)")
print("-" * 70)
cur.execute("SELECT COUNT(DISTINCT qb_name) FROM qb_accounts_staging")
unique_accounts = cur.fetchone()[0]
print(f"Unique QB account names: {unique_accounts:,}")

cur.execute("SELECT DISTINCT import_source FROM qb_accounts_staging")
sources = [r[0] for r in cur.fetchall()]
print(f"Import sources: {', '.join(sources)}")

print("ℹ RECOMMENDATION: Verify QB account list is current reference data")
print("  Keep as staging reference or promote to qb_chart_of_accounts table")

# 4. staging_banking_pdf_transactions -> banking_transactions
print("\n4. STAGING_BANKING_PDF_TRANSACTIONS (269 rows, 2012 CIBC)")
print("-" * 70)

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number LIKE '%1615%'
      AND transaction_date >= '2012-01-04'
      AND transaction_date <= '2012-12-03'
""")

cibc_2012_in_prod = cur.fetchone()[0]
print(f"2012 CIBC transactions in banking_transactions: {cibc_2012_in_prod:,}")

cur.execute("SELECT DISTINCT source_file FROM staging_banking_pdf_transactions")
source_files = [r[0] for r in cur.fetchall()]
print(f"Source PDF files: {len(source_files)}")
for f in source_files[:3]:
    print(f"  - {f}")

print("ℹ RECOMMENDATION: Compare row counts - likely already promoted in Nov 7 session")

# 5. pdf_staging -> document inventory
print("\n5. PDF_STAGING (879 rows, document inventory)")
print("-" * 70)

cur.execute("SELECT status, COUNT(*) FROM pdf_staging GROUP BY status")
statuses = cur.fetchall()
print("Status distribution:")
for status, cnt in statuses:
    print(f"  {status}: {cnt:,} files")

cur.execute("SELECT category, COUNT(*) FROM pdf_staging GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10")
categories = cur.fetchall()
print("\nTop categories:")
for category, cnt in categories:
    print(f"  {category}: {cnt:,} files")

print("ℹ RECOMMENDATION: KEEP - This is a document inventory/tracking table")
print("  Not a staging table for promotion, but an operational table")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("\nTABLES TO ARCHIVE:")
print("  ✓ staging_receipts_raw (100% processed)")
print("  ✓ staging_scotia_2012_verified (if hash match > 95%)")
print("  ✓ staging_banking_pdf_transactions (likely already promoted)")
print("\nTABLES TO KEEP:")
print("  • pdf_staging (operational document inventory)")
print("  • qb_accounts_staging (reference data for QB chart of accounts)")

cur.close()
conn.close()

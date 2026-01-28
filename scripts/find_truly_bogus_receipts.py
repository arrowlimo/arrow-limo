#!/usr/bin/env python3
"""Find truly bogus receipts in 2020-2025 (excluding legitimate accruals)."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("IDENTIFYING TRULY BOGUS RECEIPTS (2020-2025)")
print("=" * 100)

# Exclude known legitimate orphans (Heffner accruals, Insurance premiums)
print("\n1. ORPHAN RECEIPTS (Excluding known accruals):")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount),
           MIN(receipt_date) as first_date,
           MAX(receipt_date) as last_date
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND vendor_name NOT LIKE '%HEFFNER%'
    AND vendor_name NOT LIKE '%CMB%INSURANCE%'
    AND vendor_name NOT LIKE '%TD%INSURANCE%'
    GROUP BY vendor_name
    HAVING COUNT(*) >= 1
    ORDER BY SUM(gross_amount) DESC NULLS LAST
    LIMIT 30
""")
suspicious = cur.fetchall()
print(f"Top suspicious orphan vendors (no banking match):")
print(f"{'Vendor':<50} {'Count':>6} {'Amount':>15} {'Date Range'}")
print("-" * 100)
total_suspicious = 0
total_amount = 0
for vendor, count, amount, first_date, last_date in suspicious:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    vendor_display = vendor[:47] + "..." if len(vendor) > 50 else vendor
    print(f"{vendor_display:<50} {count:6} {amt_str:>15} {first_date} to {last_date}")
    total_suspicious += count
    total_amount += amount if amount else 0

print(f"\nTotal suspicious receipts: {total_suspicious:,}, ${total_amount:,.2f}")

# Focus on 2025 specifically
print("\n" + "=" * 100)
print("2025 SPECIFIC ANALYSIS (User reported 'a lot of bogus receipts')")
print("=" * 100)

cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount),
           array_agg(receipt_id ORDER BY receipt_id) as receipt_ids
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2025
    AND banking_transaction_id IS NULL
    AND vendor_name NOT LIKE '%HEFFNER%'
    GROUP BY vendor_name
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
""")
bogus_2025 = cur.fetchall()
print(f"\n2025 Orphan receipts (grouped by vendor):")
for vendor, count, amount, receipt_ids in bogus_2025:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"  {vendor[:50]:50} {count:3} receipts, {amt_str:>12}")
    if count <= 10:
        print(f"    IDs: {receipt_ids}")

# Check for actual duplicates (same vendor, date, amount)
print("\n2. TRUE DUPLICATES IN 2025 (same vendor + date + amount):")
cur.execute("""
    WITH dupe_groups AS (
        SELECT vendor_name, receipt_date::date as rdate, gross_amount, COUNT(*) as cnt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2025
        GROUP BY vendor_name, receipt_date::date, gross_amount
        HAVING COUNT(*) > 1
    )
    SELECT dg.vendor_name, dg.rdate, dg.gross_amount, dg.cnt,
           array_agg(r.receipt_id ORDER BY r.receipt_id) as ids,
           array_agg(CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'LINKED' ELSE 'ORPHAN' END) as statuses
    FROM dupe_groups dg
    JOIN receipts r ON r.vendor_name = dg.vendor_name 
                   AND r.receipt_date::date = dg.rdate 
                   AND (r.gross_amount = dg.gross_amount OR (r.gross_amount IS NULL AND dg.gross_amount IS NULL))
    GROUP BY dg.vendor_name, dg.rdate, dg.gross_amount, dg.cnt
    ORDER BY dg.cnt DESC, dg.gross_amount DESC NULLS LAST
""")
dupes_2025 = cur.fetchall()
total_dupe_receipts = 0
orphan_dupes = 0
for vendor, rdate, amount, cnt, ids, statuses in dupes_2025:
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    orphan_count = sum(1 for s in statuses if s == 'ORPHAN')
    total_dupe_receipts += cnt
    orphan_dupes += orphan_count
    if orphan_count > 0:  # Only show if there are orphans
        print(f"  {rdate} | {vendor[:40]:40} | {amt_str:>10} | {cnt} copies ({orphan_count} orphans)")
        print(f"    IDs: {ids}")

print(f"\nTotal duplicate groups in 2025: {len(dupes_2025)}")
print(f"Total orphan duplicates (safe to delete): {orphan_dupes}")

# Check for receipts with unusual patterns
print("\n3. SUSPICIOUS PATTERNS IN 2025:")

# NULL amounts
cur.execute("""
    SELECT vendor_name, COUNT(*)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2025
    AND gross_amount IS NULL
    AND banking_transaction_id IS NULL
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
null_amounts = cur.fetchall()
if null_amounts:
    print("\n  NULL amounts (no banking link):")
    for vendor, count in null_amounts[:10]:
        print(f"    {vendor[:60]:60} {count:3} receipts")

# Summary and action plan
print("\n" + "=" * 100)
print("RECOMMENDED DELETIONS")
print("=" * 100)

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND vendor_name NOT LIKE '%HEFFNER%'
    AND vendor_name NOT LIKE '%CMB%INSURANCE%'
    AND vendor_name NOT LIKE '%TD%INSURANCE%'
""")
deletable_count, deletable_amount = cur.fetchone()

print(f"""
SAFE TO DELETE (after review):
  Count: {deletable_count:,} receipts
  Amount: ${deletable_amount if deletable_amount else 0:,.2f}

Categories:
  - Orphan duplicates: {orphan_dupes} receipts
  - NULL amount orphans: Review individually
  - Created_from_banking but no actual banking: Review individually

KEEP (Legitimate Accruals):
  - HEFFNER AUTO FINANCE: 1,259 receipts (vehicle finance accruals)
  - CMB/TD INSURANCE: 5 receipts (insurance premiums)

ACTION:
  1. Review high-value orphan receipts manually
  2. Delete confirmed duplicates and bogus entries
  3. Keep Heffner and Insurance accruals (legitimate accounting)
""")

cur.close()
conn.close()

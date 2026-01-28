#!/usr/bin/env python3
"""Verify 2020-2025 receipts against banking transactions (accurate bank data period)."""

import psycopg2
import os
from collections import defaultdict

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("2020-2025 RECEIPT VERIFICATION (Accurate Banking Period)")
print("=" * 100)

# Get overall stats by year
print("\nRECEIPT COUNTS BY YEAR (2020-2025):")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as total_receipts,
        COUNT(banking_transaction_id) as banking_linked,
        COUNT(*) - COUNT(banking_transaction_id) as orphans,
        SUM(CASE WHEN banking_transaction_id IS NULL THEN gross_amount ELSE 0 END) as orphan_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")
year_stats = cur.fetchall()
for year, total, linked, orphans, orphan_amt in year_stats:
    orphan_pct = 100 * orphans / total if total > 0 else 0
    print(f"  {int(year)}: {total:5} total | {linked:5} linked ({100*linked/total:5.1f}%) | "
          f"{orphans:5} orphans ({orphan_pct:5.1f}%) | ${orphan_amt if orphan_amt else 0:,.2f}")

# Get orphan receipts by vendor for 2020-2025
print("\n" + "=" * 100)
print("ORPHAN RECEIPTS BY VENDOR (2020-2025) - LIKELY BOGUS")
print("=" * 100)

cur.execute("""
    SELECT vendor_name, 
           COUNT(*) as count, 
           SUM(gross_amount) as amount,
           MIN(receipt_date) as first_date,
           MAX(receipt_date) as last_date
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    GROUP BY vendor_name
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, SUM(gross_amount) DESC
    LIMIT 50
""")
orphan_vendors = cur.fetchall()
print(f"\nTop orphan vendors (no banking match):")
print(f"{'Vendor':<50} {'Count':>6} {'Amount':>15} {'Date Range'}")
print("-" * 100)
for vendor, count, amount, first_date, last_date in orphan_vendors:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    vendor_display = vendor[:47] + "..." if len(vendor) > 50 else vendor
    print(f"{vendor_display:<50} {count:6} {amt_str:>15} {first_date} to {last_date}")

# Check specific problem patterns
print("\n" + "=" * 100)
print("SPECIFIC PROBLEM PATTERNS (2020-2025)")
print("=" * 100)

# 1. Duplicate descriptions
print("\n1. POTENTIAL DUPLICATES (same vendor, amount, date):")
cur.execute("""
    WITH dupes AS (
        SELECT vendor_name, gross_amount, receipt_date::date as rdate, COUNT(*) as cnt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
        GROUP BY vendor_name, gross_amount, receipt_date::date
        HAVING COUNT(*) > 1
    )
    SELECT d.vendor_name, d.gross_amount, d.rdate, d.cnt,
           array_agg(r.receipt_id ORDER BY r.receipt_id) as receipt_ids,
           array_agg(CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'LINKED' ELSE 'ORPHAN' END) as statuses
    FROM dupes d
    JOIN receipts r ON r.vendor_name = d.vendor_name 
                   AND r.gross_amount = d.gross_amount 
                   AND r.receipt_date::date = d.rdate
    GROUP BY d.vendor_name, d.gross_amount, d.rdate, d.cnt
    ORDER BY d.cnt DESC, d.gross_amount DESC
    LIMIT 30
""")
duplicates = cur.fetchall()
total_dupe_receipts = 0
for vendor, amount, rdate, cnt, receipt_ids, statuses in duplicates:
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    orphan_count = sum(1 for s in statuses if s == 'ORPHAN')
    total_dupe_receipts += orphan_count
    if orphan_count > 0:
        print(f"  {rdate} | {vendor[:40]:40} | {amt_str:>12} | {cnt} copies ({orphan_count} orphans)")
        print(f"    IDs: {receipt_ids}")

print(f"\nTotal potential duplicate orphans: {total_dupe_receipts}")

# 2. Orphans with NSF flag (these might be legitimate NSF fees)
print("\n2. ORPHAN NSF RECEIPTS (may be legitimate bank fees):")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND (vendor_name LIKE '%NSF%' OR description LIKE '%NSF%')
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
nsf_orphans = cur.fetchall()
for vendor, count, amount in nsf_orphans:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"  {vendor[:60]:60} {count:5} receipts {amt_str:>12}")

# 3. Check for receipts created from banking but now orphaned
print("\n3. RECEIPTS CREATED FROM BANKING BUT NOW ORPHANED:")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND created_from_banking = true
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
banking_orphans = cur.fetchall()
if banking_orphans:
    for vendor, count, amount in banking_orphans:
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"  {vendor[:60]:60} {count:5} receipts {amt_str:>12}")
else:
    print("  None found (good!)")

# Summary
print("\n" + "=" * 100)
print("SUMMARY: 2020-2025 VERIFICATION")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(banking_transaction_id) as linked,
        COUNT(*) - COUNT(banking_transaction_id) as orphans,
        SUM(CASE WHEN banking_transaction_id IS NULL THEN gross_amount ELSE 0 END) as orphan_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
""")
total, linked, orphans, orphan_amt = cur.fetchone()
orphan_pct = 100 * orphans / total if total > 0 else 0

print(f"Total receipts (2020-2025): {total:,}")
print(f"Banking linked: {linked:,} ({100*linked/total:.1f}%)")
print(f"Orphans (NO banking match): {orphans:,} ({orphan_pct:.1f}%)")
print(f"Orphan amount: ${orphan_amt if orphan_amt else 0:,.2f}")

print("\n⚠️  RECOMMENDATION:")
print(f"Review {orphans:,} orphan receipts from 2020-2025.")
print("With accurate banking data, these are likely:")
print("  1. Import errors/duplicates")
print("  2. Manual entries without banking backup")
print("  3. System-generated placeholders")
print("\nConsider deletion after manual review of high-value items.")

cur.close()
conn.close()

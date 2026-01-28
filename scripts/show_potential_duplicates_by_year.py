#!/usr/bin/env python3
"""Show all 20 potential duplicate groups with year breakdown."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

# Get all true duplicate groups
cur.execute("""
    WITH grouped AS (
        SELECT 
            receipt_date,
            EXTRACT(YEAR FROM receipt_date) as year,
            gross_amount,
            COALESCE(canonical_vendor, vendor_name) as vendor,
            COUNT(*) as count,
            STRING_AGG(receipt_id::text, ', ' ORDER BY receipt_id) as receipt_ids,
            COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) as unique_banking_links
        FROM receipts
        WHERE exclude_from_reports = false OR exclude_from_reports IS NULL
        GROUP BY receipt_date, gross_amount, vendor
        HAVING COUNT(*) > 1
          AND (COUNT(DISTINCT banking_transaction_id) FILTER (WHERE banking_transaction_id IS NOT NULL) <= 1)
    )
    SELECT 
        year,
        receipt_date,
        gross_amount,
        vendor,
        count,
        receipt_ids,
        unique_banking_links
    FROM grouped
    ORDER BY year, receipt_date
""")

results = cur.fetchall()

print("=" * 100)
print(f"ALL {len(results)} POTENTIAL DUPLICATE GROUPS")
print("=" * 100)

# Count by year
year_counts = {}
for year, date, amount, vendor, count, ids, bank_links in results:
    year = int(year) if year else 0
    if year not in year_counts:
        year_counts[year] = 0
    year_counts[year] += 1

print("\nBREAKDOWN BY YEAR:")
print("-" * 40)
for year in sorted(year_counts.keys()):
    print(f"{year}: {year_counts[year]} groups")

print(f"\n{'Year':<6s} | {'Date':<12s} | {'Amount':>10s} | {'Vendor':<25s} | Cnt | Bank | IDs")
print("-" * 100)

for year, date, amount, vendor, count, ids, bank_links in results:
    if year is None or date is None or amount is None:
        continue
    vendor_display = str(vendor)[:25] if vendor else "Unknown"
    amt = float(amount) if amount else 0.0
    print(f"{int(year):<6d} | {str(date):<12s} | ${amt:>9.2f} | {vendor_display:25s} | {int(count):>3d} | {int(bank_links) if bank_links else 0:>4d} | {str(ids)[:30]}")

print("\n" + "=" * 100)

cur.close()
conn.close()

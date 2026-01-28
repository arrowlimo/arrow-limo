#!/usr/bin/env python3
"""
Generate summary report from receipt matching results.
"""
import csv
import os
from collections import defaultdict

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

matched_path = os.path.join(REPORT_DIR, "receipt_charter_driver_matches.csv")
unmatched_path = os.path.join(REPORT_DIR, "receipt_charter_driver_unmatched.csv")

# Read matched
matched_rows = []
with open(matched_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    matched_rows = list(reader)

# Read unmatched
unmatched_rows = []
with open(unmatched_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    unmatched_rows = list(reader)

print("=" * 100)
print("RECEIPT-CHARTER-DRIVER MATCHING SUMMARY")
print("=" * 100)

print(f"\nTotal matched: {len(matched_rows):,}")
print(f"Total unmatched: {len(unmatched_rows):,}")
print(f"Total receipts: {len(matched_rows) + len(unmatched_rows):,}")

# Matched breakdown by source
match_sources = defaultdict(int)
for row in matched_rows:
    src = row.get("match_source") or "unknown"
    match_sources[src] += 1

print("\nMatched breakdown by source:")
for src, cnt in sorted(match_sources.items(), key=lambda x: -x[1]):
    print(f"  {src:<30} {cnt:>5,} receipts")

# Driver matches
driver_matched = sum(1 for r in matched_rows if r.get("driver_match_id"))
print(f"\nDriver matches: {driver_matched:,} receipts")

# Charter matches
charter_matched = sum(1 for r in matched_rows if r.get("charter_id_matched"))
print(f"Charter matches: {charter_matched:,} receipts")

# Unmatched by vendor
unmatched_vendors = defaultdict(lambda: {"count": 0, "amount": 0.0})
for row in unmatched_rows:
    vendor = row.get("vendor_name") or "(null)"
    amount = float(row.get("amount") or 0)
    unmatched_vendors[vendor]["count"] += 1
    unmatched_vendors[vendor]["amount"] += amount

print("\nUnmatched receipts - Top 20 vendors:")
for vendor, data in sorted(unmatched_vendors.items(), key=lambda x: -x[1]["amount"])[:20]:
    print(f"  {vendor[:50]:<52} {data['count']:>5,} receipts  ${data['amount']:>12,.2f}")

print("\n" + "=" * 100)
print("REPORTS GENERATED:")
print(f"  Matched: {matched_path}")
print(f"  Unmatched: {unmatched_path}")
print("=" * 100)

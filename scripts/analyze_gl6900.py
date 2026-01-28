#!/usr/bin/env python3
"""Analyze GL 6900 (Unknown) receipts and suggest proper GL codes."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("GL 6900 (UNKNOWN) RECEIPTS ANALYSIS")
print("=" * 100 + "\n")

# Analyze GL 6900 by vendor
cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total, 
           MIN(receipt_date) as earliest, MAX(receipt_date) as latest
    FROM receipts
    WHERE gl_account_code = '6900'
    GROUP BY vendor_name
    ORDER BY total DESC
    LIMIT 30
""")

print("Top 30 vendors with GL 6900 (Unknown):\n")
total_records = 0
total_amount = 0.0

for vendor, count, total, earliest, latest in cur.fetchall():
    total_records += count
    total_amount += float(total)
    print(f"{vendor:40} | {count:4d} receipts | ${float(total):12,.2f} | {earliest.year}-{latest.year}")

print(f"\nTotal (top 30): {total_records} receipts, ${total_amount:,.2f}\n")

# Get all GL 6900 count
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE gl_account_code = '6900'")
all_count, all_amount = cur.fetchone()
print(f"All GL 6900 records: {all_count} receipts, ${all_amount:,.2f}")

# Common GL codes by category
print("\n" + "=" * 100)
print("GL CODE MAPPING SUGGESTIONS")
print("=" * 100 + "\n")

print("""
Based on vendor names, here are suggested GL code mappings:

UTILITIES (GL 5500):
  - Telus, Shaw, Allstream, AltaLink, Enmax, atco

INSURANCE (GL 6400):
  - Jevco, Cooperators, Northland, CPP, EI contributions

FUEL (GL 5306):
  - Petro Canada, Husky, Esso, Shell, Fas Gas

MEALS & ENTERTAINMENT (GL 6200):
  - Restaurants, Bars, Liquor stores

REPAIRS & MAINTENANCE (GL 5400):
  - Auto repairs, Tire shops, Mechanics

VEHICLE (GL 5200):
  - Registration, Licensing, Vehicle purchases

OFFICE SUPPLIES (GL 5100):
  - Staples, Office Depot, Paper supplies

Let me analyze the specific vendors:
""")

# Sample some GL 6900 records for manual review
cur.execute("""
    SELECT vendor_name, receipt_date, gross_amount, description
    FROM receipts
    WHERE gl_account_code = '6900'
    ORDER BY gross_amount DESC
    LIMIT 20
""")

print("\nLargest GL 6900 records (sample for categorization):\n")
for vendor, date, amount, desc in cur.fetchall():
    print(f"{vendor:40} | {date} | ${amount:8,.2f}")

cur.close()
conn.close()

print("\n✅ Analysis complete")

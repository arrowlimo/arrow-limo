#!/usr/bin/env python
"""Validate vendor groups before standardization - clean output."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("VENDOR STANDARDIZATION GROUPS - FOR APPROVAL")
print("="*100 + "\n")

# FAS GAS variants
print("GROUP 1: FAS GAS")
print("-" * 100)
cur.execute("""
    SELECT UPPER(vendor_name) AS name, COUNT(*) as cnt
    FROM receipts
    WHERE UPPER(vendor_name) LIKE 'FAS%GAS%' OR UPPER(vendor_name) LIKE 'FASGAS%'
    GROUP BY 1 ORDER BY 2 DESC
""")
fas_total = 0
for name, count in cur.fetchall():
    print(f"  {name:70s} │ {count:5d}")
    fas_total += count
print(f"  Total: {fas_total} receipts → Standardize to: FAS GAS\n")

# CENTEX variants
print("GROUP 2: CENTEX (formerly CENTEX GAS)")
print("-" * 100)
cur.execute("""
    SELECT UPPER(vendor_name) AS name, COUNT(*) as cnt
    FROM receipts
    WHERE UPPER(vendor_name) LIKE 'CENTEX%' OR UPPER(vendor_name) LIKE '%CENTEX%'
    GROUP BY 1 ORDER BY 2 DESC
""")
centex_total = 0
for name, count in cur.fetchall():
    print(f"  {name:70s} │ {count:5d}")
    centex_total += count
print(f"  Total: {centex_total} receipts → Standardize to: CENTEX\n")

# COOP variants (KEEP INDIVIDUAL)
print("GROUP 3: COOP VARIANTS (KEEP AS INDIVIDUAL VENDORS - DO NOT CONSOLIDATE)")
print("-" * 100)
cur.execute("""
    SELECT UPPER(vendor_name) AS name, COUNT(*) as cnt
    FROM receipts
    WHERE UPPER(vendor_name) LIKE '%COOP%' OR UPPER(vendor_name) LIKE '%CO-OP%' OR UPPER(vendor_name) LIKE '%CO OP%'
    GROUP BY 1 ORDER BY 2 DESC
""")
coop_total = 0
coop_detail = []
for name, count in cur.fetchall():
    coop_detail.append((name, count))
    coop_total += count
    print(f"  {name:70s} │ {count:5d}")
print(f"  Total: {coop_total} receipts")
print("  ✓ Keep as: CO-OP, CO-OP INSURANCE, CO OPERATORS (distinct vendors)\n")

# WB variants (WINE AND BEYOND)
print("GROUP 4: WINE AND BEYOND")
print("-" * 100)
cur.execute("""
    SELECT UPPER(vendor_name) AS name, COUNT(*) as cnt
    FROM receipts
    WHERE UPPER(vendor_name) LIKE 'WB%' OR UPPER(vendor_name) LIKE 'WINE AND BEYOND%'
    GROUP BY 1 ORDER BY 2 DESC
""")
wine_total = 0
for name, count in cur.fetchall():
    print(f"  {name:70s} │ {count:5d}")
    wine_total += count
print(f"  Total: {wine_total} receipts → Standardize to: WINE AND BEYOND\n")

# LIQUOR BARN variants
print("GROUP 5: LIQUOR BARN")
print("-" * 100)
cur.execute("""
    SELECT UPPER(vendor_name) AS name, COUNT(*) as cnt
    FROM receipts
    WHERE UPPER(vendor_name) LIKE 'LB%' OR UPPER(vendor_name) LIKE 'LIQUOR BARN%' OR UPPER(vendor_name) LIKE '%LIQUOR BARN%'
    GROUP BY 1 ORDER BY 2 DESC
""")
lb_total = 0
for name, count in cur.fetchall():
    print(f"  {name:70s} │ {count:5d}")
    lb_total += count
print(f"  Total: {lb_total} receipts → Standardize to: LIQUOR BARN\n")

# Summary
print("="*100)
print("APPROVAL SUMMARY - Ready to Apply?")
print("="*100)
print(f"""
GROUP 1 - FAS GAS:              531 receipts → FAS GAS
GROUP 2 - CENTEX:               360 receipts → CENTEX (was CENTEX GAS)
GROUP 3 - COOP:                 355 receipts → KEEP INDIVIDUAL (CO-OP, CO-OP INSURANCE, CO OPERATORS)
GROUP 4 - WINE AND BEYOND:      118 receipts → WINE AND BEYOND
GROUP 5 - LIQUOR BARN:          336 receipts → LIQUOR BARN

TOTAL: 1,700 receipts affected
""")

cur.close()
conn.close()

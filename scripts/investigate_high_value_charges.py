#!/usr/bin/env python3
"""Investigate high-value unclassified charges from vendor mapping analysis."""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("="*80)
print("HIGH-VALUE CHARGE INVESTIGATION")
print("="*80)

# 1. CIBC $152K Bank Charges
print("\n1. CIBC $152,455.95 (Bank Charges category)")
print("-"*80)
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount, category, payment_method
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'CIBC'
    AND category = 'Bank Charges'
    ORDER BY gross_amount DESC 
    LIMIT 30
""")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r[0]:6} | {r[1]} | {r[2][:55]:55} | ${r[3]:>9,.2f} | {r[5]}")

# Count breakdown
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'CIBC'
    AND category = 'Bank Charges'
""")
cnt, total = cur.fetchone()
print(f"\n  TOTAL: {cnt} receipts, ${total:,.2f}")

# 2. RBC $99K Vehicle Financing
print("\n\n2. RBC $99,248.14 (Vehicle Financing category)")
print("-"*80)
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount, category, payment_method
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'RBC'
    AND category = 'Vehicle Financing'
    ORDER BY gross_amount DESC 
    LIMIT 30
""")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r[0]:6} | {r[1]} | {r[2][:55]:55} | ${r[3]:>9,.2f} | {r[5]}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'RBC'
    AND category = 'Vehicle Financing'
""")
cnt, total = cur.fetchone()
print(f"\n  TOTAL: {cnt} receipts, ${total:,.2f}")

# 3. CIBC $99K Vehicle Financing
print("\n\n3. CIBC $99,248.14 (Vehicle Financing category)")
print("-"*80)
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount, category, payment_method
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'CIBC'
    AND category = 'Vehicle Financing'
    ORDER BY gross_amount DESC 
    LIMIT 30
""")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r[0]:6} | {r[1]} | {r[2][:55]:55} | ${r[3]:>9,.2f} | {r[5]}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'CIBC'
    AND category = 'Vehicle Financing'
""")
cnt, total = cur.fetchone()
print(f"\n  TOTAL: {cnt} receipts, ${total:,.2f}")

# 4. Utilities $96K bank_fees
print("\n\n4. Utilities $96,018.51 (bank_fees category)")
print("-"*80)
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount, category, payment_method
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'Utilities'
    AND category = 'bank_fees'
    ORDER BY gross_amount DESC 
    LIMIT 30
""")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r[0]:6} | {r[1]} | {r[2][:55]:55} | ${r[3]:>9,.2f} | {r[5]}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'Utilities'
    AND category = 'bank_fees'
""")
cnt, total = cur.fetchone()
print(f"\n  TOTAL: {cnt} receipts, ${total:,.2f}")

# 5. Mike Woodrow
print("\n\n5. Mike Woodrow $22,160.24 (bank_fees category) - USER SAYS: Usually rent, can be vehicle R&M")
print("-"*80)
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount, category, payment_method
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'Mike Woodrow'
    ORDER BY gross_amount DESC 
    LIMIT 35
""")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r[0]:6} | {r[1]} | {r[2][:55]:55} | ${r[3]:>9,.2f} | {r[5]}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'Mike Woodrow'
""")
cnt, total = cur.fetchone()
print(f"\n  TOTAL: {cnt} receipts, ${total:,.2f}")

# 6. Richard Michael
print("\n\n6. Richard Michael $20,284.01 (Driver Payment) - USER SAYS: Driver pay")
print("-"*80)
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount, category, payment_method
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'Richard Michael'
    ORDER BY gross_amount DESC 
    LIMIT 30
""")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(f"  {r[0]:6} | {r[1]} | {r[2][:55]:55} | ${r[3]:>9,.2f} | {r[5]}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
    AND COALESCE(canonical_vendor, vendor_name) = 'Richard Michael'
""")
cnt, total = cur.fetchone()
print(f"\n  TOTAL: {cnt} receipts, ${total:,.2f}")

cur.close()
conn.close()

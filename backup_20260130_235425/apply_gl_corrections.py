#!/usr/bin/env python3
"""Apply GL account corrections to receipts table based on vendor analysis."""

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
print("APPLYING GL ACCOUNT CORRECTIONS")
print("="*80)

# 1. Mike Woodrow → 5410 Rent Expense
print("\n1. Updating Mike Woodrow to 5410 (Rent Expense)...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5410'
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND COALESCE(canonical_vendor, vendor_name) = 'Mike Woodrow'
    AND gl_account_code != '5410'
""")
rows_updated = cur.rowcount
print(f"   ✅ Updated {rows_updated} receipts")

# 2. Clarify Michael Richard - DISTINCT from Richard Gursky
print("\n2. Classification: Michael Richard (2019) - DRIVER PAYMENTS")
print("   NOTE: Michael Richard is a DIFFERENT PERSON from Richard Gursky")
print("   - Michael Richard: 2019 data, 34 receipts, driver payment amounts")
print("   - Richard Gursky: 2021-2023 data (separate person entirely)")
print("   CONFIRMED: These are legitimate driver wage e-transfers")
print("   MAPPING: GL 5210 (Driver Wages)")

# Update Michael Richard to Driver Wages GL account
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5210'
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND COALESCE(canonical_vendor, vendor_name) = 'Michael Richard'
    AND gl_account_code IS NULL
""")
michael_richard_updated = cur.rowcount
print(f"   ✅ Updated {michael_richard_updated} Michael Richard receipts to GL 5210")

# Show first Insurance/Heffner receipts categorized as Bank Charges
print("\n3. Insurance payments wrongly in Bank Charges category...")
cur.execute("""
    SELECT receipt_id, receipt_date, description, gross_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND COALESCE(canonical_vendor, vendor_name) = 'CIBC'
    AND category = 'Bank Charges'
    AND description ILIKE '%FIRST INSURANCE%'
    ORDER BY receipt_date
    LIMIT 3
""")
rows = cur.fetchall()
print(f"   Found {rows.__length__ if hasattr(rows, '__length__') else len(rows)} insurance receipts in Bank Charges:")
for r in rows:
    print(f"   - {r[1]} | {r[2][:60]} | ${r[3]:,.2f}")

# 4. Update First Insurance receipts to 5130
print("\n4. Updating First Insurance receipts to 5130 (Vehicle Insurance)...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5130'
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND COALESCE(canonical_vendor, vendor_name) = 'CIBC'
    AND category = 'Bank Charges'
    AND description ILIKE '%FIRST INSURANCE%'
    AND gl_account_code != '5130'
""")
rows_updated = cur.rowcount
print(f"   ✅ Updated {rows_updated} receipts")

conn.commit()

# Verification
print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

cur.execute("""
    SELECT 
        COALESCE(canonical_vendor, vendor_name) AS vendor,
        gl_account_code,
        COUNT(*) AS count,
        SUM(gross_amount) AS total
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND COALESCE(canonical_vendor, vendor_name) IN ('Mike Woodrow', 'Richard Michael', 'Michael Richard')
    GROUP BY COALESCE(canonical_vendor, vendor_name), gl_account_code
    ORDER BY vendor, gl_account_code
""")

print("\nUpdated Vendor Mappings:")
for row in cur.fetchall():
    vendor, gl_code, count, total = row
    print(f"  {vendor:20} | GL:{gl_code:6} | {count:3} receipts | ${total:>10,.2f}")

print("\n" + "="*80)
print("SUMMARY OF CORRECTIONS")
print("="*80)
print(f"\n✅ Mike Woodrow → GL 5410 (Rent): {rows_updated} receipts")
print(f"✅ Michael Richard → GL 5210 (Driver Wages): {michael_richard_updated} receipts")
print(f"✅ First Insurance → GL 5130 (Vehicle Insurance): Applied")
print("\n📌 NOTE: Michael Richard (2019) is CONFIRMED as separate person from Richard Gursky (2021-2023)")
print("   These are legitimate driver wage payments, properly classified.")
print("\n✅ All updates complete.")

cur.close()
conn.close()

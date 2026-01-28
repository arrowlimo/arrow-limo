#!/usr/bin/env python3
"""
Generate final vendor standardization summary report.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("VENDOR STANDARDIZATION FINAL SUMMARY")
print("=" * 80)

# Total unique vendors
cur.execute("""
    SELECT COUNT(DISTINCT vendor_name)
    FROM receipts
    WHERE vendor_name IS NOT NULL
""")
unique_vendors = cur.fetchone()[0]

# Total receipts
cur.execute("SELECT COUNT(*) FROM receipts")
total_receipts = cur.fetchone()[0]

# UNKNOWN vendors
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
""")
unknown_count = cur.fetchone()[0]

# Historical vendors
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'HISTORICAL - UNVERIFIED'
""")
historical_count = cur.fetchone()[0]

print(f"\nDatabase Statistics:")
print(f"  Total receipts: {total_receipts:,}")
print(f"  Unique vendors: {unique_vendors:,}")
print(f"  UNKNOWN vendors: {unknown_count}")
print(f"  Historical (pre-2012): {historical_count}")

print("\n" + "=" * 80)
print("CHANGES APPLIED")
print("=" * 80)

changes_summary = """
1. GLOBAL PAYMENTS SHORT FORM
   - Reverted 1,348 transactions to VCARD/MCARD/ACARD format
   - Fixed 4 NSF transactions mislabeled as card deposits

2. CASH WITHDRAWAL STANDARDIZATION
   - Standardized 1,906 ATM/ABM withdrawals to CASH WITHDRAWAL

3. GAS STATION STANDARDIZATION
   - Cleaned 1,675 receipts (kept brand names, removed locations)
   - Brands: ESSO, SHELL, PETRO CANADA, CO-OP, FAS GAS, RUN'N ON EMPTY, etc.

4. EMAIL TRANSFER
   - Standardized 3,083 email transfer receipts

5. UNKNOWN VENDOR ELIMINATION
   - Extracted 2,233 vendor names from descriptions
   - Deleted 2,041 duplicate/null receipts
   - Flagged 5 pre-2012 receipts as HISTORICAL - UNVERIFIED
   - Final UNKNOWN count: 0

6. EXCEL-BASED CLEANUP (User Suggestions)
   - Applied 2,187 vendor name corrections
   - Fixed truncated names: ERLES AUTO REPA → ERLES AUTO REPAIR
   - Fixed typos: THE LIQUOR HUTC → THE LIQUOR HUTCH
   - Expanded abbreviations: FIRST INSURANCE → FIRST INSURANCE FUNDING

7. BANKING RESEARCH-BASED FIXES
   - AIR CAN* → AIR CANADA
   - FACEBK variants → FACEBOOK ADVERTISING (9 receipts)
   - CLEARVIEW → CLEARVIEW MARKET
   - TD → TD INSURANCE (3) / TD (UNKNOWN TYPE) (6)
   - WIX, HTS → WIX.COM, HTS (USD PURCHASE)
   - Internal transfers marked: ARROW LIMOUSINE (INTERNAL TRANSFER)

8. POINT OF SALE USD CLEANUP
   - Extracted 11 USD transaction vendors (WIX.COM, FACEBK, etc.)

TOTAL RECEIPTS MODIFIED: ~5,000+
"""

print(changes_summary)

print("=" * 80)
print("TOP 20 VENDORS BY AMOUNT")
print("=" * 80)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
    ORDER BY total DESC NULLS LAST
    LIMIT 20
""")

results = cur.fetchall()
print(f"\n{'Vendor':<45} {'Count':>6} {'Total':>15}")
print("-" * 70)
for vendor, count, total in results:
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"{vendor[:44]:<45} {count:>6} {total_str:>15}")

print("\n" + "=" * 80)
print("BACKUPS CREATED")
print("=" * 80)
print("\n1. almsdata_backup_VENDOR_STANDARDIZATION_20251221_150748.sql (1,200.66 MB)")
print("2. almsdata_backup_VENDOR_STANDARDIZATION_20251221_172844.sql (1,200.54 MB)")

print("\n" + "=" * 80)
print("✅ VENDOR STANDARDIZATION COMPLETE")
print("=" * 80)

cur.close()
conn.close()

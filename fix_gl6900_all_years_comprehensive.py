"""
Fix GL 6900 - ALL YEARS Comprehensive Fix
Applies all identified patterns across entire database (not limited to 2012-2015)
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

# Create backup table
backup_name = f"receipts_backup_gl6900_all_years_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_name}")
cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM receipts WHERE gl_account_code = '6900'")
conn.commit()
print(f"Backed up {cur.rowcount} receipts\n")

# Track total updates
total_updated = 0

print("="*80)
print("APPLYING FIXES TO ALL YEARS (2012-2026)")
print("="*80)

# Group 1: Bank Fees -> GL 5700
print("\n[1] BANK FEES -> GL 5700...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5700',
        category = 'Banking & Financial',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND (vendor_name IN ('PAPER STATEMENT FEE', 'STATEMENT FEE', 'PAPER STMT FEE', 'SBAP FEE',
                           'INTERAC FEE', 'PAPER STMNT FEE', 'DRAFT FEE')
           OR vendor_name LIKE '%STATEMENT FEE%'
           OR vendor_name LIKE '%INTERAC FEE%')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 2: Loan Payments -> GL 6300
print("\n[2] LOAN PAYMENTS -> GL 6300...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '6300',
        category = 'Loan Payment - Principal',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND (vendor_name IN ('HEFFNER AUTO FINANCE', 'MCAP SERVICES-RMG MORTGAGES', 'CAPITAL ONE MASTERCARD')
           OR vendor_name LIKE 'MCAP SERVICE%'
           OR category = 'Banking Transaction')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 3: Vehicle Maintenance & Parts -> GL 5100
print("\n[3] VEHICLE MAINTENANCE & PARTS -> GL 5100...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5100',
        category = 'Vehicle Maintenance & Repairs',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND (vendor_name IN ('NORTHLAND RADIATOR', 'MIKASA PERFORMANCE', 'PART SOURCE', 
                           'WINDSHIELD SURGEONS', 'AUTOMOTIVE VILLAGE')
           OR description LIKE '%AUTOMOTIVE%')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 4: Office Supplies -> GL 5400
print("\n[4] OFFICE SUPPLIES & ELECTRONICS -> GL 5400...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5400',
        category = 'Office Supplies & Equipment',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND vendor_name IN ('COPIES NOW', 'OFFICE SUPPLIES', 'FUTURE SHOP', 'ELECTRONICS',
                          'CELLCOM WIRELESS INC')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 5: Airport Fees -> GL 5300
print("\n[5] AIRPORT FEES -> GL 5300...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5300',
        category = 'Airport Fees & Tolls',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND (vendor_name LIKE '%CALGARY AIRPORT%'
           OR vendor_name LIKE '%AIRPORT%')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 6: Utilities -> GL 5400
print("\n[6] UTILITIES -> GL 5400...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5400',
        category = 'Utilities - Electric/Gas',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND vendor_name IN ('ENMAX')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 7: WCB (Workers Compensation) -> GL 5200
print("\n[7] WCB (Workers Compensation) -> GL 5200...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5200',
        category = 'Payroll - WCB',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND vendor_name = 'WCB'
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 8: Insurance -> GL 5800
print("\n[8] INSURANCE -> GL 5800...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5800',
        category = 'Insurance - General',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND (vendor_name IN ('ALL SERVICE INSURNACE', 'EQUITY PREMIUM FINANCE')
           OR vendor_name LIKE '%INTACT INS%')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 9: Work Clothing -> GL 5800
print("\n[9] WORK CLOTHING -> GL 5800...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5800',
        category = 'Uniforms & Work Clothing',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND vendor_name IN ('MARKS WORK WEARHOUSE')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 10: Personal Items -> Personal
print("\n[10] PERSONAL ITEMS -> Personal...")
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Personal',
        category = 'Personal - Meals & Entertainment'
    WHERE gl_account_code = '6900'
      AND vendor_name IN ('TONY ROMAS', 'MONGOLIE GRILL', 'SUSHI SUSHI', 'MACDONALDS', 
                          'THE RANCH HOUSE', 'TOMMY GUNS', 'WOK BOX', 'ARBYS', 'MCDONALD''S',
                          'VILLAGE CHIROPRACTOR', 'CINEPLES', '7-ELEVEN', 'THE BAY', 
                          'COSTCO', 'CITY CENTER VACUUM', 'BED BATH & BEYOND', 'CLEARVIEW DENTAL')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

# Group 11: Garnishment/Attachment Orders -> GL 6200 (Other Deductions)
print("\n[11] GARNISHMENTS -> GL 6200...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '6200',
        category = 'Garnishment/Attachment Order',
        business_personal = 'Business'
    WHERE gl_account_code = '6900'
      AND vendor_name LIKE '%ATTACHMENT ORDER%'
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts")

conn.commit()

print("\n" + "="*80)
print(f"TOTAL UPDATED: {total_updated} receipts fixed")
print("="*80)

# Show remaining GL 6900 count
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE gl_account_code = '6900'
""")
remaining_count, remaining_amount = cur.fetchone()
print(f"\nRemaining GL 6900 items (ALL YEARS): {remaining_count:,} receipts, ${remaining_amount:,.2f}")

# Show by year
print("\nRemaining by year:")
cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date) as year, COUNT(*)
    FROM receipts
    WHERE gl_account_code = '6900'
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")
for year, cnt in cur.fetchall():
    if year:
        print(f"  {int(year)}: {cnt:>4} items")

cur.close()
conn.close()

print(f"\n[DONE] Comprehensive GL 6900 fix completed!")
print(f"Backup saved as: {backup_name}")

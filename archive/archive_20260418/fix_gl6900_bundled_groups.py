"""
Fix GL 6900 Bundled Groups - Batch update identifiable categories
Updates 7 groups of receipts from GL 6900 to proper GL codes
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
backup_name = f"receipts_backup_gl6900_bundle_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_name}")
cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM receipts WHERE gl_account_code = '6900'")
conn.commit()
print(f"Backed up {cur.rowcount} receipts\n")

# Track total updates
total_updated = 0

# Group 1: Bank Fees -> GL 5700 (Banking & Financial)
print("[1] Updating BANK FEES to GL 5700...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5700',
        category = 'Banking & Financial'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('PAPER STATEMENT FEE', 'STATEMENT FEE', 'PAPER STMT FEE', 'SBAP FEE')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} bank fee receipts\n")

# Group 2: Loan Payments -> GL 6300 (Loan Principal)
print("[2] Updating LOAN PAYMENTS to GL 6300...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '6300',
        category = 'Loan Payment - Principal'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('HEFFNER AUTO FINANCE', 'MCAP SERVICES-RMG MORTGAGES')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} loan payment receipts\n")

# Group 3: Vehicle Maintenance -> GL 5100 (Vehicle Operating)
print("[3] Updating VEHICLE MAINTENANCE to GL 5100...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5100',
        category = 'Vehicle Maintenance & Repairs'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('NORTHLAND RADIATOR', 'MIKASA PERFORMANCE')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} vehicle maintenance receipts\n")

# Group 4: Office Supplies -> GL 5400 (Office & Administrative)
print("[4] Updating OFFICE SUPPLIES to GL 5400...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5400',
        category = 'Office Supplies & Equipment'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('COPIES NOW', 'OFFICE SUPPLIES', 'FUTURE SHOP', 'ELECTRONICS')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} office supply receipts\n")

# Group 5: Airport Fees -> GL 5300 (Customer Service)
print("[5] Updating AIRPORT FEES to GL 5300...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5300',
        category = 'Airport Fees & Tolls'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('CALGARY AIRPORT', 'CALGARY AIRPORT AUTHORITY')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} airport fee receipts\n")

# Group 6: Restaurants -> Personal
print("[6] Updating RESTAURANTS to Personal...")
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Personal',
        category = 'Personal - Meals & Entertainment'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('TONY ROMAS', 'MONGOLIE GRILL', 'SUSHI SUSHI', 'MACDONALDS', 'THE RANCH HOUSE', 'TOMMY GUNS')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} restaurant receipts to Personal\n")

# Group 7: Insurance -> GL 5800 (Other Business Expenses)
print("[7] Updating INSURANCE to GL 5800...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5800',
        category = 'Insurance - General'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('ALL SERVICE INSURNACE', 'EQUITY PREMIUM FINANCE')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} insurance receipts\n")

conn.commit()

print("="*80)
print(f"TOTAL UPDATED: {total_updated} receipts moved from GL 6900")
print("="*80)

# Show remaining GL 6900 count
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
""")
remaining_count, remaining_amount = cur.fetchone()
print(f"\nRemaining GL 6900 items (2012-2015): {remaining_count:,} receipts, ${remaining_amount:,.2f}")

# Update business_personal for the fixed items (except restaurants which are already Personal)
print("\nSetting business_personal = 'Business' for newly classified items...")
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Business'
    WHERE gl_account_code IN ('5700', '6300', '5100', '5400', '5300', '5800')
      AND business_personal IN ('NEEDS_REVIEW', 'false', NULL)
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
""")
print(f"Updated business_personal for {cur.rowcount} receipts")

conn.commit()

cur.close()
conn.close()

print("\n[DONE] GL 6900 bundle fix completed successfully!")
print(f"Backup saved as: {backup_name}")

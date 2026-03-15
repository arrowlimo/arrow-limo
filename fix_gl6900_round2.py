"""
Fix GL 6900 Bundled Groups - ROUND 2
Updates additional identifiable patterns from remaining GL 6900 items
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
backup_name = f"receipts_backup_gl6900_round2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_name}")
cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM receipts WHERE gl_account_code = '6900'")
conn.commit()
print(f"Backed up {cur.rowcount} receipts\n")

# Track total updates
total_updated = 0

# Group 1: Items already categorized as Personal but still in GL 6900
print("[1] Updating items already marked 'Personal - Meals & Entertainment'...")
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Personal'
    WHERE gl_account_code = '6900'
      AND category = 'Personal - Meals & Entertainment'
      AND business_personal != 'Personal'
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} receipts to Personal classification\n")

# Group 2: More bank fees
print("[2] Updating MORE BANK FEES to GL 5700...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5700',
        category = 'Banking & Financial'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('INTERAC FEE', 'PAPER STMNT FEE', 'DRAFT FEE')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} bank fee receipts\n")

# Group 3: More loan/mortgage payments
print("[3] Updating MORE LOAN PAYMENTS to GL 6300...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '6300',
        category = 'Loan Payment - Principal'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND (vendor_name LIKE 'MCAP SERVICE%' OR vendor_name = 'CAPITAL ONE MASTERCARD')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} loan/credit payment receipts\n")

# Group 4: Vehicle parts
print("[4] Updating VEHICLE PARTS to GL 5100...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5100',
        category = 'Vehicle Parts & Supplies'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('PART SOURCE')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} vehicle parts receipts\n")

# Group 5: Utilities
print("[5] Updating UTILITIES to GL 5400...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5400',
        category = 'Utilities - Electric/Gas'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name = 'ENMAX'
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} utility receipts\n")

# Group 6: WCB (Workers Compensation Board) -> Payroll expense
print("[6] Updating WCB to GL 5200...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5200',
        category = 'Payroll - WCB'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name = 'WCB'
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} WCB receipts\n")

# Group 7: More restaurants and personal items
print("[7] Updating MORE PERSONAL ITEMS...")
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Personal',
        category = 'Personal - Meals & Entertainment'
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
      AND vendor_name IN ('WOK BOX', 'ARBYS', 'MCDONALD''S', 'VILLAGE CHIROPRACTOR', 
                          'CINEPLES', '7-ELEVEN', 'THE BAY', 'COSTCO', 'CITY CENTER VACUUM')
""")
count = cur.rowcount
total_updated += count
print(f"    Updated {count} personal item receipts\n")

conn.commit()

print("="*80)
print(f"TOTAL UPDATED: {total_updated} receipts moved from GL 6900")
print("="*80)

# Show remaining GL 6900 count
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE gl_account_code = '6900'
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
""")
remaining_count, remaining_amount = cur.fetchone()
print(f"\nRemaining GL 6900 items (2012-2015): {remaining_count:,} receipts, ${remaining_amount:,.2f}")

# Update business_personal for the fixed items (except personal ones)
print("\nSetting business_personal = 'Business' for newly classified items...")
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Business'
    WHERE gl_account_code IN ('5700', '6300', '5100', '5400', '5200')
      AND business_personal IN ('NEEDS_REVIEW', 'false', NULL, 'BUSINESS')
      AND receipt_date BETWEEN '2012-01-01' AND '2015-12-31'
""")
print(f"Updated business_personal for {cur.rowcount} receipts")

conn.commit()

cur.close()
conn.close()

print("\n[DONE] GL 6900 Round 2 bundle fix completed successfully!")
print(f"Backup saved as: {backup_name}")

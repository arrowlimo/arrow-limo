"""
Fix business_personal Classification for CRA Audit Compliance
Auto-classifies receipts as 'Business' based on GL codes and categories
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

print("="*100)
print("BUSINESS_PERSONAL CLASSIFICATION FIX")
print("="*100)

# Step 1: Preview what will be updated
print("\nSTEP 1: PREVIEW OF CHANGES")
print("-"*100)

cur.execute("""
    SELECT 
        CASE 
            WHEN coa.account_type IN ('COGS', 'Expense') THEN 'Business (by GL type)'
            WHEN r.category IN (
                'Fuel', 'FUEL', 'fuel',
                'Vehicle Maintenance', 'Vehicle Financing', 'Vehicle Lease', 'Vehicle Rental/Maintenance',
                'Insurance', 'Insurance - Vehicle Liability',
                'Driver Expense', 'Driver Pay',
                'Rent', 'rent',
                'Telecommunications',
                'Office Supplies',
                'Bank Fees',
                'Client Beverages', 'Client Entertainment',
                'Government Fees',
                'Internet Bill Payment',
                'LOANS'
            ) THEN 'Business (by category)'
            ELSE 'Other'
        END as reason,
        COUNT(*) as count,
        SUM(r.gross_amount) as total
    FROM receipts r
    LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
    WHERE (r.business_personal IS NULL 
           OR r.business_personal NOT IN ('Business', 'BUSINESS', 'business'))
      AND (
          coa.account_type IN ('COGS', 'Expense')
          OR r.category IN (
              'Fuel', 'FUEL', 'fuel',
              'Vehicle Maintenance', 'Vehicle Financing', 'Vehicle Lease', 'Vehicle Rental/Maintenance',
              'Insurance', 'Insurance - Vehicle Liability',
              'Driver Expense', 'Driver Pay',
              'Rent', 'rent',
              'Telecommunications',
              'Office Supplies',
              'Bank Fees',
              'Client Beverages', 'Client Entertainment',
              'Government Fees',
              'Internet Bill Payment',
              'LOANS'
          )
      )
    GROUP BY reason
    ORDER BY total DESC
""")

preview = cur.fetchall()
total_to_update = sum(r[1] for r in preview)
total_amount = sum(r[2] or 0 for r in preview)

print(f"\n{'Reason':<30} {'Count':>10} {'Amount':>18}")
print("-"*62)
for reason, count, amount in preview:
    print(f"{reason:<30} {count:>10,} ${amount:>17,.2f}")
print("-"*62)
print(f"{'TOTAL TO UPDATE':<30} {total_to_update:>10,} ${total_amount:>17,.2f}")

# Step 2: Create backup
print("\n" + "="*100)
print("STEP 2: CREATING BACKUP")
print("-"*100)

backup_table = f"receipts_backup_business_classification_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

cur.execute(f"""
    CREATE TABLE {backup_table} AS 
    SELECT * FROM receipts
    WHERE business_personal IS NULL 
       OR business_personal NOT IN ('Business', 'BUSINESS', 'business')
""")

cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]
print(f"✓ Backup created: {backup_table}")
print(f"✓ {backup_count:,} receipts backed up")

# Step 3: Apply updates
print("\n" + "="*100)
print("STEP 3: APPLYING CLASSIFICATION UPDATES")
print("-"*100)

# Update based on GL Code type (COGS or Expense)
cur.execute("""
    UPDATE receipts r
    SET business_personal = 'Business'
    FROM chart_of_accounts coa
    WHERE r.gl_account_code = coa.account_code
      AND coa.account_type IN ('COGS', 'Expense')
      AND (r.business_personal IS NULL 
           OR r.business_personal NOT IN ('Business', 'BUSINESS', 'business'))
""")
gl_count = cur.rowcount
print(f"✓ Updated {gl_count:,} receipts based on GL code type (COGS/Expense)")

# Update based on category (for receipts without GL codes or with non-expense GL codes)
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Business'
    WHERE (business_personal IS NULL 
           OR business_personal NOT IN ('Business', 'BUSINESS', 'business'))
      AND category IN (
          'Fuel', 'FUEL', 'fuel',
          'Vehicle Maintenance', 'Vehicle Financing', 'Vehicle Lease', 'Vehicle Rental/Maintenance',
          'Insurance', 'Insurance - Vehicle Liability',
          'Driver Expense', 'Driver Pay',
          'Rent', 'rent',
          'Telecommunications',
          'Office Supplies',
          'Bank Fees',
          'Client Beverages', 'Client Entertainment',
          'Government Fees',
          'Internet Bill Payment',
          'LOANS',
          'Meals & Entertainment',
          'Contract Labor',
          'Supplies'
      )
""")
cat_count = cur.rowcount
print(f"✓ Updated {cat_count:,} receipts based on business category")

total_updated = gl_count + cat_count
print(f"\n{'='*100}")
print(f"TOTAL UPDATED: {total_updated:,} receipts")

# Step 4: Verify results
print("\n" + "="*100)
print("STEP 4: VERIFICATION")
print("-"*100)

cur.execute("""
    SELECT 
        business_personal,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY business_personal
    ORDER BY count DESC
""")

print(f"\n{'Classification':<30} {'Count':>10} {'Amount':>18}")
print("-"*62)
for classification, count, amount in cur.fetchall():
    print(f"{str(classification or 'NULL'):<30} {count:>10,} ${amount or 0:>17,.2f}")

# Check remaining unclassified business expenses
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts r
    LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
    WHERE coa.account_type IN ('COGS', 'Expense')
      AND (r.business_personal IS NULL 
           OR r.business_personal NOT IN ('Business', 'BUSINESS', 'business'))
""")

remaining_count, remaining_amt = cur.fetchone()

print("\n" + "="*100)
if remaining_count > 0:
    print(f"⚠ Still unclassified: {remaining_count:,} business expense receipts (${remaining_amt or 0:,.2f})")
    print("  These may need manual review or have unusual GL codes")
else:
    print("✓ SUCCESS: All business expenses are now classified!")

# Step 5: Commit changes
print("\n" + "="*100)
print("STEP 5: COMMIT CHANGES")
print("-"*100)

conn.commit()
print("✓ All changes committed to database")
print(f"✓ Backup table: {backup_table}")

print("\n" + "="*100)
print("CLASSIFICATION FIX COMPLETE")
print("="*100)
print(f"""
Summary:
- {total_updated:,} receipts updated to 'Business'
- ${total_amount:,.2f} in business expenses properly classified
- Backup saved to: {backup_table}
- Classification based on GL codes (COGS/Expense) and business categories
""")

cur.close()
conn.close()

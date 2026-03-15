"""
Classify Remaining NULL business_personal Receipts
Handles: Income, Personal, Asset, Liability, and flags Unknown for review
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
print("CLASSIFY REMAINING NULL RECEIPTS")
print("="*100)

# Create backup
backup_table = f"receipts_backup_null_classification_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM receipts WHERE business_personal IS NULL")
cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]
print(f"\n✓ Backup created: {backup_table} ({backup_count:,} receipts)")

print("\n" + "="*100)
print("STEP 1: CLASSIFY INCOME/REVENUE ITEMS")
print("="*100)

# Income items should be marked as "Income" (not business expense)
cur.execute("""
    UPDATE receipts r
    SET business_personal = 'Income'
    FROM chart_of_accounts coa
    WHERE r.gl_account_code = coa.account_code
      AND coa.account_type IN ('Income', 'Revenue')
      AND r.business_personal IS NULL
""")
income_gl_count = cur.rowcount

cur.execute("""
    UPDATE receipts
    SET business_personal = 'Income'
    WHERE business_personal IS NULL
      AND (category ILIKE '%income%'
           OR category = 'revenue'
           OR category ILIKE '%payment received%')
""")
income_cat_count = cur.rowcount

print(f"✓ Classified {income_gl_count:,} items as 'Income' (by GL code)")
print(f"✓ Classified {income_cat_count:,} items as 'Income' (by category)")

print("\n" + "="*100)
print("STEP 2: CLASSIFY PERSONAL EXPENSES")
print("="*100)

cur.execute("""
    UPDATE receipts
    SET business_personal = 'Personal'
    WHERE business_personal IS NULL
      AND (category ILIKE '%personal%'
           OR category ILIKE '%groceries%'
           OR category = 'Food - Personal'
           OR category = 'Groceries - Personal'
           OR category = 'meals_entertainment'
           OR category = 'entertainment_beverages')
""")
personal_count = cur.rowcount
print(f"✓ Classified {personal_count:,} items as 'Personal' (owner draws)")

print("\n" + "="*100)
print("STEP 3: CLASSIFY ASSET & LIABILITY ITEMS")
print("="*100)

cur.execute("""
    UPDATE receipts r
    SET business_personal = 'Asset'
    FROM chart_of_accounts coa
    WHERE r.gl_account_code = coa.account_code
      AND coa.account_type = 'Asset'
      AND r.business_personal IS NULL
""")
asset_count = cur.rowcount
print(f"✓ Classified {asset_count:,} items as 'Asset' (balance sheet items)")

cur.execute("""
    UPDATE receipts r
    SET business_personal = 'Liability'
    FROM chart_of_accounts coa
    WHERE r.gl_account_code = coa.account_code
      AND coa.account_type = 'Liability'
      AND r.business_personal IS NULL
""")
liability_count = cur.rowcount
print(f"✓ Classified {liability_count:,} items as 'Liability' (loans/debts)")

print("\n" + "="*100)
print("STEP 4: CLASSIFY REMAINING BUSINESS EXPENSES")
print("="*100)

# Classify "Business expense" category as Business
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Business'
    WHERE business_personal IS NULL
      AND (category = 'Business expense'
           OR category = 'uncategorized_expenses')
""")
biz_exp_count = cur.rowcount
print(f"✓ Classified {biz_exp_count:,} 'Business expense' items as 'Business'")

# Classify Banking Transaction category (mostly loan payments)
cur.execute("""
    UPDATE receipts
    SET business_personal = 'Business'
    WHERE business_personal IS NULL
      AND category = 'Banking Transaction'
      AND vendor_name ILIKE '%HEFFNER%'
""")
loan_count = cur.rowcount
print(f"✓ Classified {loan_count:,} HEFFNER loan payments as 'Business'")

print("\n" + "="*100)
print("STEP 5: FLAG UNKNOWN ITEMS FOR MANUAL REVIEW")
print("="*100)

# Mark GL 6900 Unknown items as needing review
cur.execute("""
    UPDATE receipts
    SET business_personal = 'NEEDS_REVIEW'
    WHERE business_personal IS NULL
      AND (gl_account_code IN ('6900', '6400', '6000', '6100', '6200', '6300', '6950')
           OR category = 'Unknown'
           OR category IS NULL)
""")
review_count = cur.rowcount
print(f"✓ Flagged {review_count:,} items as 'NEEDS_REVIEW' (Unknown GL codes or categories)")

print("\n" + "="*100)
print("STEP 6: VERIFICATION & SUMMARY")
print("="*100)

cur.execute("""
    SELECT 
        business_personal,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY business_personal
    ORDER BY 
        CASE 
            WHEN business_personal IN ('Business', 'BUSINESS', 'business') THEN 1
            WHEN business_personal = 'Personal' THEN 2
            WHEN business_personal = 'Income' THEN 3
            WHEN business_personal = 'NEEDS_REVIEW' THEN 4
            ELSE 5
        END,
        count DESC
""")

print(f"\n{'Classification':<30} {'Count':>10} {'Amount':>18}")
print("-"*62)
total_classified = 0
for classification, count, amount in cur.fetchall():
    print(f"{str(classification or 'NULL'):<30} {count:>10,} ${amount or 0:>17,.2f}")
    if classification and classification != 'NULL':
        total_classified += count

# Check remaining NULL
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE business_personal IS NULL")
null_remaining, null_amt = cur.fetchone()

print("\n" + "="*100)
total_updates = income_gl_count + income_cat_count + personal_count + asset_count + liability_count + biz_exp_count + loan_count + review_count

print(f"TOTAL UPDATES: {total_updates:,} receipts")
print(f"Remaining NULL: {null_remaining:,} (${null_amt or 0:,.2f})")

# Commit
conn.commit()
print(f"\n✓ All changes committed")
print(f"✓ Backup: {backup_table}")

print("\n" + "="*100)
print("NEXT STEPS FOR 'NEEDS_REVIEW' ITEMS:")
print("="*100)

cur.execute("""
    SELECT 
        gl_account_code,
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE business_personal = 'NEEDS_REVIEW'
    GROUP BY gl_account_code, category
    ORDER BY total DESC
    LIMIT 10
""")

print(f"\n{'GL Code':<10} {'Category':<30} {'Count':>10} {'Amount':>18}")
print("-"*72)
for gl, cat, count, amount in cur.fetchall():
    print(f"{gl or 'NONE':<10} {(cat or 'NULL')[:30]:<30} {count:>10,} ${amount or 0:>17,.2f}")

print("""
These items need manual review to determine:
1. Is it a business expense? → Update to 'Business'
2. Is it personal/owner use? → Update to 'Personal'
3. Is it income/revenue? → Update to 'Income'
4. Should it be deleted (duplicate, error)?

GL code 6900 "Unknown" should be replaced with proper GL codes from your
chart of accounts based on what each expense actually represents.
""")

cur.close()
conn.close()

print("\n" + "="*100)
print("CLASSIFICATION COMPLETE")
print("="*100)

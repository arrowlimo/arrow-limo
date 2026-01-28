"""
Analyze all category/classification fields across receipts, banking, and other tables
to identify variations and create a standardized chart of accounts.
"""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost",
    port="5432"
)

cur = conn.cursor()

print("=" * 100)
print("CATEGORY STANDARDIZATION ANALYSIS")
print("=" * 100)

# 1. Receipts - Classifications
print("\n1. RECEIPTS - CURRENT CLASSIFICATIONS")
print("-" * 100)

cur.execute("""
    SELECT 
        classification,
        sub_classification,
        COUNT(*) as count,
        SUM(COALESCE(expense, 0)) as total_expense
    FROM receipts
    WHERE classification IS NOT NULL 
       OR sub_classification IS NOT NULL
    GROUP BY classification, sub_classification
    ORDER BY count DESC
    LIMIT 50
""")

print(f"{'Classification':40} {'Sub-Classification':30} {'Count':>8} {'Total':>15}")
print("-" * 100)
for row in cur.fetchall():
    classification, sub_class, count, total = row
    classification = (classification or 'NULL')[:39]
    sub_class = (sub_class or 'NULL')[:29]
    print(f"{classification:40} {sub_class:30} {count:8,} ${total:13,.2f}")

# 2. Receipts - Expense Accounts
print("\n2. RECEIPTS - EXPENSE ACCOUNT CODES")
print("-" * 100)

cur.execute("""
    SELECT 
        expense_account,
        COUNT(*) as count,
        SUM(COALESCE(expense, 0)) as total_expense
    FROM receipts
    WHERE expense_account IS NOT NULL
    GROUP BY expense_account
    ORDER BY count DESC
""")

print(f"{'Expense Account':40} {'Count':>8} {'Total':>15}")
print("-" * 100)
for row in cur.fetchall():
    account, count, total = row
    account = (account or 'NULL')[:39]
    print(f"{account:40} {count:8,} ${total:13,.2f}")

# 3. Banking - Categories
print("\n3. BANKING TRANSACTIONS - CATEGORIES")
print("-" * 100)

cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0)) as total_amount
    FROM banking_transactions
    WHERE category IS NOT NULL
    GROUP BY category
    ORDER BY count DESC
""")

print(f"{'Category':40} {'Count':>8} {'Total':>15}")
print("-" * 100)
for row in cur.fetchall():
    category, count, total = row
    category = (category or 'NULL')[:39]
    print(f"{category:40} {count:8,} ${total:13,.2f}")

# 4. Look for vendor patterns to suggest categories
print("\n4. COMMON VENDORS (for category suggestions)")
print("-" * 100)

cur.execute("""
    SELECT 
        vendor_name,
        classification,
        sub_classification,
        COUNT(*) as count,
        SUM(COALESCE(expense, 0)) as total
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name, classification, sub_classification
    HAVING COUNT(*) >= 3
    ORDER BY count DESC
    LIMIT 30
""")

print(f"{'Vendor':35} {'Classification':25} {'Sub-Class':20} {'Cnt':>5} {'Total':>12}")
print("-" * 100)
for row in cur.fetchall():
    vendor, classification, sub_class, count, total = row
    vendor = (vendor or '')[:34]
    classification = (classification or '')[:24]
    sub_class = (sub_class or '')[:19]
    print(f"{vendor:35} {classification:25} {sub_class:20} {count:5,} ${total:10,.2f}")

# 5. Find variations of similar categories
print("\n5. IDENTIFYING CATEGORY VARIATIONS")
print("-" * 100)

cur.execute("""
    SELECT DISTINCT 
        UPPER(TRIM(classification)) as classification_normalized,
        STRING_AGG(DISTINCT classification, ', ') as variations,
        COUNT(DISTINCT classification) as variation_count,
        SUM(cnt) as total_count
    FROM (
        SELECT 
            classification,
            COUNT(*) as cnt
        FROM receipts
        WHERE classification IS NOT NULL
        GROUP BY classification
    ) sub
    GROUP BY UPPER(TRIM(classification))
    HAVING COUNT(DISTINCT classification) > 1
    ORDER BY total_count DESC
""")

results = cur.fetchall()
if results:
    print(f"{'Standard Name':30} {'Variations':50} {'Var#':>5} {'Total':>8}")
    print("-" * 100)
    for row in results:
        normalized, variations, var_count, total = row
        normalized = (normalized or '')[:29]
        variations = (variations or '')[:49]
        print(f"{normalized:30} {variations:50} {var_count:5,} {total:8,}")
else:
    print("No major variations found (good - classifications are consistent)")

# 6. Expense type patterns
print("\n6. EXPENSE TYPES FROM RECEIPTS")
print("-" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN UPPER(vendor_name) LIKE '%FAS GAS%' OR UPPER(vendor_name) LIKE '%ESSO%' 
                 OR UPPER(vendor_name) LIKE '%PETRO%' OR UPPER(vendor_name) LIKE '%SHELL%' THEN 'FUEL'
            WHEN UPPER(vendor_name) LIKE '%LIQUOR%' OR UPPER(classification) LIKE '%BEVERAGE%' THEN 'CLIENT BEVERAGES'
            WHEN UPPER(vendor_name) LIKE '%AIRPORT%' THEN 'PARKING'
            WHEN UPPER(classification) LIKE '%VEHICLE%' OR UPPER(classification) LIKE '%AUTO%' 
                 OR UPPER(sub_classification) LIKE '%REPAIR%' THEN 'VEHICLE MAINTENANCE'
            WHEN UPPER(classification) LIKE '%UNIFORMS%' THEN 'UNIFORMS'
            WHEN UPPER(classification) LIKE '%OFFICE%' THEN 'OFFICE SUPPLIES'
            WHEN UPPER(vendor_name) LIKE '%TELUS%' OR UPPER(vendor_name) LIKE '%SHAW%' 
                 OR UPPER(vendor_name) LIKE '%PHONE%' THEN 'TELECOMMUNICATIONS'
            WHEN UPPER(classification) LIKE '%RENT%' THEN 'RENT'
            ELSE 'OTHER'
        END as expense_type,
        COUNT(*) as count,
        SUM(COALESCE(expense, 0)) as total
    FROM receipts
    WHERE expense IS NOT NULL AND expense > 0
    GROUP BY expense_type
    ORDER BY total DESC
""")

print(f"{'Expense Type':30} {'Count':>8} {'Total':>15}")
print("-" * 100)
for row in cur.fetchall():
    exp_type, count, total = row
    print(f"{exp_type:30} {count:8,} ${total:13,.2f}")

# 7. List all unique classifications for review
print("\n7. ALL UNIQUE CLASSIFICATIONS (for standardization)")
print("-" * 100)

cur.execute("""
    SELECT DISTINCT classification
    FROM receipts
    WHERE classification IS NOT NULL
    ORDER BY classification
""")

classifications = [row[0] for row in cur.fetchall()]
print(f"Total unique classifications: {len(classifications)}")
print("\nClassifications list:")
for i, classification in enumerate(classifications, 1):
    print(f"  {i:3}. {classification}")

# 8. List all unique sub-classifications
print("\n8. ALL UNIQUE SUB-CLASSIFICATIONS")
print("-" * 100)

cur.execute("""
    SELECT DISTINCT sub_classification
    FROM receipts
    WHERE sub_classification IS NOT NULL
    ORDER BY sub_classification
""")

sub_classifications = [row[0] for row in cur.fetchall()]
print(f"Total unique sub-classifications: {len(sub_classifications)}")
print("\nSub-classifications list:")
for i, sub_class in enumerate(sub_classifications, 1):
    print(f"  {i:3}. {sub_class}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
print("\nNext: Create standardized chart of accounts mapping all variations")

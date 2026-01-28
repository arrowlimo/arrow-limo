"""
Step 1: Find all receipts marked as personal
Explore how personal expenses are flagged in the system
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

conn = get_connection()
cur = conn.cursor()

# First, check receipts table structure
print("=" * 80)
print("RECEIPTS TABLE STRUCTURE - Personal Expense Fields")
print("=" * 80)

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts'
    ORDER BY ordinal_position
""")

personal_related_columns = []
all_columns = cur.fetchall()

for col_name, col_type in all_columns:
    if 'personal' in col_name.lower() or 'owner' in col_name.lower() or 'paul' in col_name.lower():
        print(f"  🔴 {col_name}: {col_type}")
        personal_related_columns.append(col_name)

print(f"\nTotal columns in receipts: {len(all_columns)}")
if personal_related_columns:
    print(f"Personal-related columns found: {personal_related_columns}")
else:
    print("No 'personal', 'owner', or 'paul' fields found. Checking alternative names...")

# Check for alternative personal tracking
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts'
    AND (column_name LIKE '%personal%' OR column_name LIKE '%owner%' OR column_name LIKE '%draw%' OR column_name LIKE '%category%')
    ORDER BY column_name
""")

alt_columns = [row[0] for row in cur.fetchall()]
if alt_columns:
    print(f"\nAlternative columns: {alt_columns}")

# Check for category/description patterns indicating personal use
print("\n" + "=" * 80)
print("CHECKING DESCRIPTION PATTERNS FOR 'PERSONAL' RECEIPTS")
print("=" * 80)

cur.execute("""
    SELECT DISTINCT description 
    FROM receipts 
    WHERE description ILIKE '%personal%' OR description ILIKE '%smokes%' OR description ILIKE '%paul%'
    ORDER BY description
    LIMIT 20
""")

personal_descriptions = cur.fetchall()
if personal_descriptions:
    print(f"\nFound {len(personal_descriptions)} distinct descriptions with 'personal' pattern:")
    for desc in personal_descriptions:
        print(f"  • {desc[0][:80]}")
else:
    print("No descriptions found with 'personal', 'smokes', or 'paul' patterns")

# Check vendor names for personal patterns
print("\n" + "=" * 80)
print("CHECKING VENDOR NAMES FOR PERSONAL EXPENSE INDICATORS")
print("=" * 80)

cur.execute("""
    SELECT DISTINCT vendor_name, COUNT(*) as count
    FROM receipts 
    WHERE vendor_name ILIKE '%personal%' 
       OR vendor_name ILIKE '%smokes%'
       OR vendor_name ILIKE '%alcohol%'
       OR vendor_name ILIKE '%liquor%'
       OR vendor_name ILIKE '%private%'
    GROUP BY vendor_name
    ORDER BY count DESC
""")

vendor_results = cur.fetchall()
if vendor_results:
    print(f"\nFound {len(vendor_results)} vendors with personal expense indicators:")
    for vendor, count in vendor_results:
        print(f"  • {vendor}: {count} receipts")

# Check GL account codes used for personal expenses
print("\n" + "=" * 80)
print("CHECKING GL CODES FOR PERSONAL/OWNER ACCOUNTS")
print("=" * 80)

cur.execute("""
    SELECT account_code, account_name, account_type
    FROM chart_of_accounts
    WHERE account_name ILIKE '%personal%' 
       OR account_name ILIKE '%owner%' 
       OR account_name ILIKE '%draw%'
       OR account_name ILIKE '%paul%'
    ORDER BY account_code
""")

gl_personal = cur.fetchall()
if gl_personal:
    print(f"\nFound {len(gl_personal)} GL accounts for personal/owner tracking:")
    for code, name, acct_type in gl_personal:
        print(f"  • {code}: {name} ({acct_type})")
else:
    print("No personal/owner GL codes found")

# Check if there's an owner_personal_amount field
print("\n" + "=" * 80)
print("CHECKING FOR OWNER_PERSONAL_AMOUNT FIELD")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*) as has_value
    FROM receipts
    WHERE owner_personal_amount IS NOT NULL AND owner_personal_amount != 0
""")

owner_personal_count = cur.fetchone()[0]
print(f"Receipts with owner_personal_amount > 0: {owner_personal_count}")

if owner_personal_count > 0:
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, owner_personal_amount, 
               receipt_date, description
        FROM receipts
        WHERE owner_personal_amount IS NOT NULL AND owner_personal_amount != 0
        ORDER BY receipt_date DESC
        LIMIT 10
    """)
    print("\nTop 10 receipts with owner_personal_amount:")
    for rid, vendor, gross, personal, date, desc in cur.fetchall():
        print(f"  #{rid} | {date} | {vendor[:30]:30s} | Gross: ${gross:8.2f} | Personal: ${personal:8.2f}")

# Check for is_driver_reimbursement (might indicate non-personal)
print("\n" + "=" * 80)
print("CHECKING FOR CATEGORY/EXPENSE TYPE PATTERNS")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*), is_driver_reimbursement
    FROM receipts
    WHERE is_driver_reimbursement IS NOT NULL
    GROUP BY is_driver_reimbursement
""")

reimbursement_counts = cur.fetchall()
for count, is_reimb in reimbursement_counts:
    print(f"  is_driver_reimbursement={is_reimb}: {count} receipts")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("1. Identify the field/method used to mark personal expenses")
print("2. Query all receipts marked as personal")
print("3. Identify Barb Peacock etransfers")
print("4. Match dates and amounts")
print("5. Create owner income entries")

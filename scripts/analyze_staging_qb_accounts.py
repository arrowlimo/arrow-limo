"""
Analyze staging_qb_accounts table (formerly staging_driver_pay).

Nov 7 2025 findings indicated this table was misnamed - contains QuickBooks 
General Ledger accounts, not driver payroll data. This script analyzes:
1. Data quality issues (NULL values, $0.00 amounts, invalid dates)
2. Column structure and what data is actually present
3. Duplicate detection against existing GL tables
4. Promotion potential for valid data
"""

import os
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 80)
print("STAGING_QB_ACCOUNTS ANALYSIS")
print("=" * 80)
print(f"Analysis date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Get table structure first
print("1. TABLE STRUCTURE")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'staging_qb_accounts'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()
print(f"Total columns: {len(columns)}")
print("\nColumn details:")
for col_name, data_type, nullable in columns:
    print(f"  {col_name:<30} {data_type:<20} {'NULL' if nullable == 'YES' else 'NOT NULL'}")

# Basic counts
print("\n2. BASIC STATISTICS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT file_id) as unique_files,
        MIN(txn_date) as earliest_date,
        MAX(txn_date) as latest_date
    FROM staging_qb_accounts
""")

total_rows, unique_files, earliest, latest = cur.fetchone()
print(f"Total rows: {total_rows:,}")
print(f"Unique files: {unique_files:,}")
print(f"Date range: {earliest} to {latest}")

# Check for Nov 7 documented issues
print("\n3. DATA QUALITY ISSUES (from Nov 7 findings)")
print("-" * 80)

# Issue 1: All driver_id NULL
cur.execute("SELECT COUNT(*) FROM staging_qb_accounts WHERE driver_id IS NULL")
null_ids = cur.fetchone()[0]
print(f"NULL driver_id: {null_ids:,} ({null_ids/total_rows*100:.1f}%)")

# Issue 2: All monetary amounts $0.00
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE gross_amount = 0 OR gross_amount IS NULL) as zero_gross,
        COUNT(*) FILTER (WHERE net_amount = 0 OR net_amount IS NULL) as zero_net,
        SUM(gross_amount) as total_gross,
        SUM(net_amount) as total_net
    FROM staging_qb_accounts
""")

zero_gross, zero_net, total_gross, total_net = cur.fetchone()
print(f"Zero gross_amount: {zero_gross:,} ({zero_gross/total_rows*100:.1f}%)")
print(f"Zero net_amount: {zero_net:,} ({zero_net/total_rows*100:.1f}%)")
print(f"Total gross: ${total_gross or 0:,.2f}")
print(f"Total net: ${total_net or 0:,.2f}")

# Issue 3: Invalid dates (1969-12-31 epoch artifacts)
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE txn_date < '1970-01-01') as pre_1970,
        COUNT(*) FILTER (WHERE txn_date = '1969-12-31') as epoch_date
    FROM staging_qb_accounts
""")

pre_1970, epoch_date = cur.fetchone()
print(f"Pre-1970 dates: {pre_1970:,}")
print(f"Epoch date (1969-12-31): {epoch_date:,}")

# Issue 4: Column misalignment (driver_name contains dates)
cur.execute("""
    SELECT COUNT(*) 
    FROM staging_qb_accounts
    WHERE driver_name ~ '^\d{1,2}/\d{1,2}/\d{4}$'
""")

date_in_name = cur.fetchone()[0]
print(f"Date patterns in driver_name: {date_in_name:,} ({date_in_name/total_rows*100:.1f}%)")

# What's actually in driver_name?
print("\n4. DRIVER_NAME FIELD ANALYSIS (should be account names?)")
print("-" * 80)
cur.execute("""
    SELECT driver_name, COUNT(*) as cnt
    FROM staging_qb_accounts
    WHERE driver_name IS NOT NULL AND driver_name != ''
      AND driver_name !~ '^\d{1,2}/\d{1,2}/\d{4}$'  -- Exclude date patterns
    GROUP BY driver_name
    ORDER BY cnt DESC
    LIMIT 30
""")

print("Top 30 non-date values in driver_name field:")
for name, cnt in cur.fetchall():
    print(f"  {name:<50} {cnt:>7,} rows")

# Check pay_type field (might indicate account types)
print("\n5. PAY_TYPE FIELD (might be account types or transaction types)")
print("-" * 80)
cur.execute("""
    SELECT pay_type, COUNT(*) as cnt
    FROM staging_qb_accounts
    WHERE pay_type IS NOT NULL AND pay_type != ''
    GROUP BY pay_type
    ORDER BY cnt DESC
    LIMIT 30
""")

pay_types = cur.fetchall()
if pay_types:
    print("Pay type distribution:")
    for pay_type, cnt in pay_types:
        print(f"  {pay_type:<40} {cnt:>7,} rows")
else:
    print("No pay_type values found (all NULL/empty)")

# Check memo field
print("\n6. MEMO FIELD ANALYSIS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE memo IS NOT NULL AND memo != '') as has_memo,
        COUNT(*) as total
    FROM staging_qb_accounts
""")

has_memo, total = cur.fetchone()
print(f"Rows with memo: {has_memo:,} ({has_memo/total*100:.1f}%)")

if has_memo > 0:
    cur.execute("""
        SELECT memo, COUNT(*) as cnt
        FROM staging_qb_accounts
        WHERE memo IS NOT NULL AND memo != ''
        GROUP BY memo
        ORDER BY cnt DESC
        LIMIT 20
    """)
    
    print("\nSample memo values:")
    for memo, cnt in cur.fetchall():
        memo_display = (memo[:60] + '...') if len(memo) > 60 else memo
        print(f"  {memo_display:<65} {cnt:>6,} rows")

# Sample actual rows
print("\n7. SAMPLE DATA ROWS")
print("-" * 80)
cur.execute("""
    SELECT 
        id, file_id, txn_date, driver_name, pay_type, 
        gross_amount, net_amount, memo
    FROM staging_qb_accounts
    WHERE driver_name IS NOT NULL 
      AND driver_name != ''
      AND driver_name !~ '^\d'  -- Exclude date patterns
    ORDER BY file_id, id
    LIMIT 10
""")

print("Sample rows (excluding date-in-name errors):")
for row in cur.fetchall():
    id, file_id, txn_date, driver_name, pay_type, gross, net, memo = row
    memo_display = (memo[:40] + '...') if memo and len(memo) > 40 else (memo or '')
    print(f"\nID {id} (File {file_id}):")
    print(f"  Date: {txn_date}")
    print(f"  Name: {driver_name}")
    print(f"  Type: {pay_type}")
    print(f"  Gross: ${gross or 0:.2f} | Net: ${net or 0:.2f}")
    print(f"  Memo: {memo_display}")

# Check for actual QB account data
print("\n8. QUICKBOOKS ACCOUNT DETECTION")
print("-" * 80)

# Common QB account patterns
qb_patterns = [
    ('Revenue', "driver_name ILIKE '%revenue%' OR driver_name ILIKE '%income%'"),
    ('Expense', "driver_name ILIKE '%expense%' OR driver_name ILIKE '%cost%'"),
    ('Asset', "driver_name ILIKE '%asset%' OR driver_name ILIKE '%equipment%'"),
    ('Liability', "driver_name ILIKE '%liability%' OR driver_name ILIKE '%payable%'"),
    ('Bank', "driver_name ILIKE '%bank%' OR driver_name ILIKE '%checking%'"),
    ('Account Receivable', "driver_name ILIKE '%receivable%'"),
    ('GST/HST', "driver_name ILIKE '%gst%' OR driver_name ILIKE '%hst%' OR driver_name ILIKE '%tax%'"),
]

for pattern_name, pattern_sql in qb_patterns:
    cur.execute(f"SELECT COUNT(*) FROM staging_qb_accounts WHERE {pattern_sql}")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  {pattern_name}: {count:,} rows")

print("\n9. COMPARISON WITH EXISTING QB TABLES")
print("-" * 80)

# Check if data matches journal or unified_general_ledger
cur.execute("""
    SELECT COUNT(DISTINCT account_name) as accounts, 
           COUNT(*) as entries,
           MIN(transaction_date) as earliest,
           MAX(transaction_date) as latest
    FROM unified_general_ledger
""")

ugl_accounts, ugl_entries, ugl_earliest, ugl_latest = cur.fetchone()
print(f"unified_general_ledger: {ugl_accounts:,} accounts, {ugl_entries:,} entries")
print(f"  Date range: {ugl_earliest} to {ugl_latest}")

cur.execute("""
    SELECT COUNT(DISTINCT "Account") as accounts,
           COUNT(*) as entries,
           MIN("Date") as earliest,
           MAX("Date") as latest
    FROM journal
""")

j_accounts, j_entries, j_earliest, j_latest = cur.fetchone()
print(f"journal: {j_accounts:,} accounts, {j_entries:,} entries")
print(f"  Date range: {j_earliest} to {j_latest}")

# Check qb_accounts_staging
cur.execute("""
    SELECT COUNT(*) as rows,
           COUNT(DISTINCT name) as unique_names
    FROM qb_accounts_staging
""")

qb_staging_rows, qb_staging_names = cur.fetchone()
print(f"qb_accounts_staging: {qb_staging_rows:,} rows, {qb_staging_names:,} unique account names")

print("\n" + "=" * 80)
print("ANALYSIS SUMMARY")
print("=" * 80)
print("\nKEY FINDINGS:")
print(f"1. Data quality: {zero_gross/total_rows*100:.1f}% have $0.00 amounts")
print(f"2. Column misalignment: {date_in_name/total_rows*100:.1f}% have dates in driver_name")
print(f"3. Missing linkage: {null_ids/total_rows*100:.1f}% missing driver_id")
print(f"4. Invalid dates: {pre_1970:,} pre-1970 dates (epoch artifacts)")
print("\nRECOMMENDATION:")
print("- Requires data cleansing before promotion")
print("- Need to re-import from source files with correct column mappings")
print("- Alternative: Drop table if data already exists in unified_general_ledger")

cur.close()
conn.close()

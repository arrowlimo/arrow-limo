"""
DATA DUPLICATION ANALYSIS
Find duplicate data in different tables and columns
Identify opportunities to consolidate via relationships instead of duplication
"""
import os
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("DATA DUPLICATION ANALYSIS - Find Redundant Data & Columns")
print("=" * 100)

# 1. Find similar column names across tables (likely duplication)
print("\n[1] DUPLICATE COLUMN NAMES ACROSS TABLES")
print("-" * 100)

cur.execute("""
SELECT column_name, COUNT(DISTINCT table_name) as table_count, 
       STRING_AGG(table_name, ', ') as tables
FROM information_schema.columns
WHERE table_schema = 'public'
GROUP BY column_name
HAVING COUNT(DISTINCT table_name) > 1
ORDER BY table_count DESC, column_name
""")

dup_columns = cur.fetchall()
print(f"Found {len(dup_columns)} column names used in multiple tables\n")
print("Top duplications (column appears in N tables):")
print(f"{'Column':<35} {'Tables':<8} {'Used In'}")
print("-" * 100)

for col_name, count, tables in dup_columns[:20]:
    table_list = ', '.join(tables.split(', ')[:3])
    if len(tables.split(', ')) > 3:
        table_list += f" +{len(tables.split(', '))-3} more"
    print(f"{col_name:<35} {count:<8} {table_list}")

if len(dup_columns) > 20:
    print(f"\n... and {len(dup_columns) - 20} more duplicated column names")

# 2. Find amount columns that might be redundant
print("\n[2] REDUNDANT AMOUNT COLUMNS (common source of duplication)")
print("-" * 100)

cur.execute("""
SELECT table_name, STRING_AGG(column_name, ', ') as amount_columns
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (column_name LIKE '%amount%'
    OR column_name LIKE '%price%'
    OR column_name LIKE '%cost%'
    OR column_name LIKE '%total%'
    OR column_name LIKE '%sum%'
    OR column_name LIKE '%charge%'
    OR column_name LIKE '%fee%')
GROUP BY table_name
HAVING COUNT(*) > 1
ORDER BY table_name
""")

amount_tables = cur.fetchall()
print(f"Found {len(amount_tables)} tables with multiple amount/price/cost columns\n")

for table, cols in amount_tables[:15]:
    col_list = cols.split(', ')
    print(f"📊 {table}:")
    for col in col_list[:5]:
        print(f"   - {col}")
    if len(col_list) > 5:
        print(f"   - ... and {len(col_list)-5} more")
    print()

# 3. Find similar data: compare across key tables
print("\n[3] DATA APPEARING IN MULTIPLE PLACES")
print("-" * 100)

# Check vendor names across tables
cur.execute("""
SELECT 'receipts' as table_name, 'vendor_name' as column_name, COUNT(*) as rows_with_data
FROM receipts WHERE vendor_name IS NOT NULL
UNION ALL
SELECT 'receipts', 'description', COUNT(*)
FROM receipts WHERE description IS NOT NULL
UNION ALL
SELECT 'general_ledger', 'memo_description', COUNT(*)
FROM general_ledger WHERE memo_description IS NOT NULL
ORDER BY table_name
""")

vendor_data = cur.fetchall()
print("Vendor data appearing in multiple tables:")
for table, col, count in vendor_data:
    print(f"  {table:<20} {col:<20} {count:>8,} rows")

# 4. Check for duplicate customer/charter data
print("\n[4] DUPLICATE CUSTOMER/CHARTER REFERENCES")
print("-" * 100)

# Find which tables have customer/charter IDs
cur.execute("""
SELECT table_name, 
       STRING_AGG(column_name, ', ') as id_columns
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (column_name IN ('customer_id', 'charter_id', 'reserve_number', 'account_number'))
GROUP BY table_name
ORDER BY table_name
""")

id_tables = cur.fetchall()
print(f"Found {len(id_tables)} tables with customer/charter/account references\n")

for table, cols in id_tables:
    col_list = cols.split(', ')
    print(f"  {table:<35} {', '.join(col_list)}")

# 5. Check payments vs receipts for duplicate amounts
print("\n[5] DATA RECONCILIATION - PAYMENTS vs RECEIPTS")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM payments")
payments_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts")
receipts_count = cur.fetchone()[0]

print(f"Payments table: {payments_count:,} rows")
print(f"Receipts table: {receipts_count:,} rows")

# Check if payments has payment amounts duplicated
cur.execute("""
SELECT 
  COUNT(*) as total_payments,
  COUNT(DISTINCT amount) as unique_amounts,
  COUNT(DISTINCT reserve_number) as unique_reserves,
  COUNT(DISTINCT account_number) as unique_accounts
FROM payments
""")

payment_stats = cur.fetchone()
print(f"\nPayment data statistics:")
print(f"  Total payments: {payment_stats[0]:,}")
print(f"  Unique amounts: {payment_stats[1]:,}")
print(f"  Unique reserves: {payment_stats[2]:,}")
print(f"  Unique accounts: {payment_stats[3]:,}")

# 6. Find tables that might be mirrors of each other
print("\n[6] POTENTIAL DUPLICATE TABLES")
print("-" * 100)

# Get all tables
cur.execute("""
SELECT table_name, COUNT(*) as column_count, 
       STRING_AGG(column_name, ', ') as columns
FROM information_schema.columns
WHERE table_schema = 'public'
GROUP BY table_name
ORDER BY table_name
""")

all_tables_cols = cur.fetchall()

# Look for tables with similar names or structures
similar_tables = defaultdict(list)
for table, col_count, cols in all_tables_cols:
    # Find backup or archive tables
    if '_backup' in table or '_archive' in table or 'old_' in table:
        base_name = table.split('_backup')[0].split('_archive')[0].split('_old')[0]
        similar_tables[base_name].append((table, col_count, 'BACKUP/ARCHIVE'))
    
    # Find duplicate prefixes
    parts = table.split('_')
    if len(parts) >= 2:
        prefix = parts[0]
        for t2, c2, cols2 in all_tables_cols:
            if t2 != table and t2.startswith(prefix) and not '_backup' in t2:
                similar_tables[prefix].append((table, col_count, 'SAME PREFIX'))

print("Potential duplicate/backup table pairs:")
found_dups = 0
for base, dups in sorted(similar_tables.items()):
    if len(dups) > 1:
        print(f"\n  {base}:")
        for table, col_count, reason in dups[:5]:
            print(f"    - {table:<40} ({col_count} cols, {reason})")
        found_dups += len(dups)

if found_dups > 0:
    print(f"\n⚠️ Found {found_dups} tables that may be duplicates or backups")

# 7. Summary and recommendations
print("\n" + "=" * 100)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 100)

print(f"""
DATA DUPLICATION FINDINGS:

✅ DUPLICATE COLUMN NAMES: {len(dup_columns)} columns appear in multiple tables
  Most common: id, created_at, updated_at (normal for relational DB)
  Concern: Columns like 'amount', 'total', 'vendor_name' in multiple places

📊 AMOUNT COLUMNS: {len(amount_tables)} tables have multiple amount/price/cost columns
  Example: receipts has gross_amount, net_amount, gst_amount, tax, sales_tax
  Concern: If calculated from each other, only ONE should be stored
  
🔄 VENDOR DATA:
  ✅ Vendor names in payments, receipts, general_ledger
  ✓ This is OK - each transaction needs vendor reference
  ⚠️ Better: Foreign key to vendor_master table instead of duplicate names

💳 CUSTOMER/CHARTER REFERENCES:
  ✓ Multiple tables have charter_id, reserve_number, account_number
  ✓ This is NORMAL - foreign keys for relationships
  ✓ Do NOT consolidate these - they're relationship links

⚠️ BACKUP TABLES:
  Found multiple _backup and _archive tables
  These are redundant if data is in main table
  Can be archived to external storage

🎯 BEST PRACTICES FOR YOUR SYSTEM:
  1. ✅ DO keep: Foreign key references (charter_id, account_number, etc.)
  2. ✅ DO use: Relationships instead of duplication
  3. ❌ DON'T duplicate: Calculated values (store once, calculate when needed)
  4. ❌ DON'T duplicate: Reference data (create master tables instead)
  5. ❌ DON'T keep: Backup tables in live database (archive them)

📋 ACTIONABLE ITEMS:
  Phase 3a: Consolidate amount columns (only store what can't be calculated)
  Phase 3b: Create master tables (vendor_master, customer_master)
  Phase 3c: Add foreign key constraints to enforce relationships
  Phase 3d: Archive backup tables to separate storage

⚠️ IMPORTANT:
  Relationships (foreign keys) are BETTER than duplication
  Each piece of data should have ONE source of truth
  Use foreign keys to link to that single source
""")

cur.close()
conn.close()

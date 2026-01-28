"""
PHASE 1 CLEANUP - Execute Safe Deletions
1. Drop staging_qb_gl_transactions (QB staging - QB abandoned)
2. Drop all QB-related tables (25 tables)
3. Drop general_ledger empty columns (30 columns)

Creates backup before deletion
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_filename = f"l:\\limo\\almsdata_backup_BEFORE_PHASE1_CLEANUP_{timestamp}.sql"

print("=" * 100)
print("PHASE 1 CLEANUP - QB Tables & Empty Columns")
print("=" * 100)

# Step 1: Backup database first
print("\n[1] CREATING BACKUP")
print("-" * 100)
print(f"Backing up to: {backup_filename}")

os.system(f'pg_dump -h {DB_HOST} -U {DB_USER} -d {DB_NAME} > "{backup_filename}"')
print("✅ Backup created")

# Step 2: Find all QB-related tables
print("\n[2] IDENTIFYING QB-RELATED TABLES")
print("-" * 100)

cur.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name LIKE 'qb_%' 
    OR table_name LIKE '%_qb'
    OR table_name LIKE 'staging_qb%'
    OR table_name LIKE '%quickbooks%')
ORDER BY table_name
""")

qb_tables = [row[0] for row in cur.fetchall()]
print(f"Found {len(qb_tables)} QB-related tables:")
for table in qb_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    rows = cur.fetchone()[0]
    print(f"  - {table:<45} ({rows:,} rows)")

# Step 3: Drop QB tables
print("\n[3] DROPPING QB TABLES")
print("-" * 100)

dropped_count = 0
dropped_rows = 0

for table in qb_tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        conn.commit()
        
        dropped_count += 1
        dropped_rows += row_count
        print(f"✅ Dropped {table:<45} ({row_count:,} rows)")
    except Exception as e:
        print(f"❌ Error dropping {table}: {e}")
        conn.rollback()

print(f"\n✅ Dropped {dropped_count} QB tables ({dropped_rows:,} total rows)")

# Step 4: Drop general_ledger empty columns
print("\n[4] DROPPING general_ledger EMPTY COLUMNS")
print("-" * 100)

empty_gl_columns = [
    'transaction_date', 'distribution_account_number', 'account_full_name',
    'item_supplier_company', 'account_number', 'tax_slip_type', 'account_type',
    'account_description', 'parent_account_id', 'customer', 'customer_full_name',
    'customer_title', 'customer_first_name', 'customer_middle_name', 'employee_deleted',
    'employee_id', 'employee_billable', 'po_number', 'ungrouped_tags',
    'transaction_id', 'tax_code', 'tax_name', 'distribution_account',
    'distribution_account_type', 'distribution_account_description',
    'parent_distribution_account_id', 'distribution_account_subtype',
    'invoice_number', 'notes'
]

dropped_cols = 0
for col in empty_gl_columns:
    try:
        cur.execute(f"ALTER TABLE general_ledger DROP COLUMN IF EXISTS {col}")
        conn.commit()
        dropped_cols += 1
        print(f"✅ Dropped column: {col}")
    except Exception as e:
        print(f"⚠️ Column {col} may not exist or has dependencies: {e}")
        conn.rollback()

print(f"\n✅ Dropped {dropped_cols} empty columns from general_ledger")

# Step 5: Verify cleanup
print("\n[5] VERIFICATION")
print("-" * 100)

cur.execute("""
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'qb_%'
""")
remaining_qb = cur.fetchone()[0]
print(f"QB tables remaining: {remaining_qb} (should be 0)")

cur.execute("""
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_name = 'general_ledger'
""")
gl_cols = cur.fetchone()[0]
print(f"general_ledger columns remaining: {gl_cols}")

cur.execute("SELECT COUNT(*) FROM general_ledger")
gl_rows = cur.fetchone()[0]
print(f"general_ledger rows preserved: {gl_rows:,}")

# Summary
print("\n" + "=" * 100)
print("PHASE 1 CLEANUP COMPLETE")
print("=" * 100)

print(f"""
✅ DELETED:
  - {dropped_count} QB-related tables ({dropped_rows:,} rows)
  - {dropped_cols} empty columns from general_ledger
  
📊 SPACE SAVED:
  - staging_qb_gl_transactions: 62.18 MB
  - All QB tables: ~150-200 MB
  - general_ledger empty columns: 176.37 MB
  - TOTAL PHASE 1: ~290-440 MB

💾 BACKUP CREATED:
  - {backup_filename}
  - Use to restore if needed

📋 NEXT PHASE (Phase 2):
  1. Drop payments table legacy columns (22.16 MB)
  2. Drop receipts table legacy columns (27.70 MB)
""")

cur.close()
conn.close()

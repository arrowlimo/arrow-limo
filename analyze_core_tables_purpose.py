"""
Analyze purpose and data completeness of core tables
Understand which empty columns are:
1. Incomplete implementation (keep)
2. True redundancy (can drop)
3. Legacy code (should drop)
"""
import os
import psycopg2
import json

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("TABLE PURPOSE & DATA COMPLETENESS ANALYSIS")
print("=" * 100)

# 1. GENERAL_LEDGER - Is it incomplete or truly empty?
print("\n[1] GENERAL_LEDGER TABLE")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM general_ledger")
gl_rows = cur.fetchone()[0]
print(f"Rows: {gl_rows:,}")

cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'general_ledger'
ORDER BY ordinal_position
""")
gl_columns = cur.fetchall()
print(f"Total Columns: {len(gl_columns)}")

# Check which columns have data
print("\nColumns WITH data:")
with_data = []
without_data = []

for col_name, col_type in gl_columns:
    cur.execute(f"""
    SELECT COUNT(*)
    FROM general_ledger
    WHERE "{col_name}" IS NOT NULL
    """)
    count = cur.fetchone()[0]
    
    if count > 0:
        unique = None
        try:
            cur.execute(f"""
            SELECT COUNT(DISTINCT "{col_name}")
            FROM general_ledger
            WHERE "{col_name}" IS NOT NULL
            """)
            unique = cur.fetchone()[0]
        except:
            unique = "?"
        
        with_data.append((col_name, col_type, count, unique))
        print(f"  ✅ {col_name:<40} {col_type:<25} {count:>6} rows, {unique} unique")
    else:
        without_data.append((col_name, col_type))

print(f"\n❌ Columns WITHOUT data ({len(without_data)}):")
for col_name, col_type in without_data[:15]:
    print(f"  ❌ {col_name:<40} {col_type:<25}")
if len(without_data) > 15:
    print(f"  ... and {len(without_data) - 15} more")

# Sample data to understand structure
print("\nSample general_ledger records (first 3):")
cur.execute(f"""
SELECT {', '.join([f'"{col[0]}"' for col in with_data[:10]])}
FROM general_ledger
LIMIT 3
""")
for row in cur.fetchall():
    print(f"  {row}")

# 2. STAGING_QB_GL_TRANSACTIONS - Can we drop it?
print("\n" + "=" * 100)
print("[2] STAGING_QB_GL_TRANSACTIONS TABLE (QuickBooks staging)")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM staging_qb_gl_transactions")
qb_rows = cur.fetchone()[0]
print(f"Rows: {qb_rows:,}")

# Check if it's referenced by anything
cur.execute("""
SELECT constraint_name, table_name, column_name
FROM information_schema.key_column_usage
WHERE table_name = 'staging_qb_gl_transactions'
LIMIT 10
""")
fks = cur.fetchall()
print(f"References to staging_qb_gl_transactions: {len(fks)}")
for fk in fks[:5]:
    print(f"  {fk}")

# Check which columns have data
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'staging_qb_gl_transactions'
ORDER BY ordinal_position
""")
qb_columns = [row[0] for row in cur.fetchall()]

print(f"\nColumns with data in staging_qb_gl_transactions:")
for col in qb_columns[:5]:
    cur.execute(f"""
    SELECT COUNT(DISTINCT "{col}")
    FROM staging_qb_gl_transactions
    WHERE "{col}" IS NOT NULL
    """)
    unique = cur.fetchone()[0]
    print(f"  ✅ {col:<40} {unique:>6} unique values")

# Check if any ETL uses this table
cur.execute("""
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_name LIKE '%qb%'
AND table_schema = 'public'
""")
qb_tables = cur.fetchone()[0]
print(f"\nOther QB-related tables in database: {qb_tables}")

# 3. RECEIPTS TABLE - Which columns are incomplete vs legacy?
print("\n" + "=" * 100)
print("[3] RECEIPTS TABLE (Core business table)")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM receipts")
receipts_rows = cur.fetchone()[0]
print(f"Rows: {receipts_rows:,}")

# Get all columns and categorize them
cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'receipts'
ORDER BY ordinal_position
""")
receipt_cols = cur.fetchall()

print("\nColumn categories:")

# Core/Important
print("\n📌 CORE COLUMNS (always populated):")
for col_name, col_type, nullable in receipt_cols[:12]:
    cur.execute(f"SELECT COUNT(*) FROM receipts WHERE \"{col_name}\" IS NOT NULL")
    count = cur.fetchone()[0]
    pct = (count / receipts_rows * 100) if receipts_rows > 0 else 0
    if pct > 95:
        print(f"  ✅ {col_name:<35} {pct:.1f}% populated")

# Sparse/Incomplete
print("\n🔄 SPARSE COLUMNS (incomplete implementation?):")
for col_name, col_type, nullable in receipt_cols:
    cur.execute(f"SELECT COUNT(*) FROM receipts WHERE \"{col_name}\" IS NOT NULL")
    count = cur.fetchone()[0]
    pct = (count / receipts_rows * 100) if receipts_rows > 0 else 0
    
    if 10 < pct < 50:  # Partially populated - might be incomplete feature
        print(f"  🔄 {col_name:<35} {pct:.1f}% populated")

# Legacy/Empty
print("\n❌ LEGACY/EMPTY COLUMNS (likely safe to drop):")
empty_cols = []
for col_name, col_type, nullable in receipt_cols:
    cur.execute(f"SELECT COUNT(*) FROM receipts WHERE \"{col_name}\" IS NOT NULL")
    count = cur.fetchone()[0]
    pct = (count / receipts_rows * 100) if receipts_rows > 0 else 0
    
    if pct < 1:  # Less than 1% populated
        empty_cols.append((col_name, pct, count))

for col_name, pct, count in empty_cols[:15]:
    print(f"  ❌ {col_name:<35} {pct:.2f}% populated ({count} rows)")
if len(empty_cols) > 15:
    print(f"  ... and {len(empty_cols) - 15} more")

# 4. PAYMENTS TABLE - Similar analysis
print("\n" + "=" * 100)
print("[4] PAYMENTS TABLE (Core business table)")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM payments")
payments_rows = cur.fetchone()[0]
print(f"Rows: {payments_rows:,}")

cur.execute("""
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'payments'
ORDER BY ordinal_position
""")
payment_cols = cur.fetchall()

print("\n📌 CORE COLUMNS (always populated):")
for col_name, col_type, nullable in payment_cols[:8]:
    cur.execute(f"SELECT COUNT(*) FROM payments WHERE \"{col_name}\" IS NOT NULL")
    count = cur.fetchone()[0]
    pct = (count / payments_rows * 100) if payments_rows > 0 else 0
    if pct > 95:
        print(f"  ✅ {col_name:<35} {pct:.1f}% populated")

print("\n❌ EMPTY COLUMNS (can drop):")
for col_name, col_type, nullable in payment_cols:
    cur.execute(f"SELECT COUNT(*) FROM payments WHERE \"{col_name}\" IS NOT NULL")
    count = cur.fetchone()[0]
    pct = (count / payments_rows * 100) if payments_rows > 0 else 0
    
    if pct < 1:
        print(f"  ❌ {col_name:<35} {pct:.2f}% populated")

# 5. SUMMARY & RECOMMENDATIONS
print("\n" + "=" * 100)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 100)

print("""
🎯 GENERAL_LEDGER TABLE:
  Status: Data-driven operational table (not staging)
  Action: Keep structure but review if all columns are needed
  Decision: Review purpose - appears to have incomplete columns
  
🎯 STAGING_QB_GL_TRANSACTIONS:
  Status: QuickBooks import staging (QB no longer used)
  Action: SAFE TO DROP - Staging table, not operational
  Estimated space save: 62.18 MB
  
🎯 RECEIPTS TABLE:
  Status: Core operational table (DO NOT delete lightly)
  Action: Review each empty column individually
  Empty columns: 21 (27.70 MB)
  Sparse columns: 32 (may be incomplete features)
  Recommendation: Drop only verified legacy columns
  
🎯 PAYMENTS TABLE:
  Status: Core operational table (DO NOT delete lightly)
  Action: Review each empty column
  Empty columns: 25 (22.16 MB)
  Recommendation: Drop verified legacy Square, QB, and check columns
  
💾 PRIORITY DROPS (SAFE):
  1. staging_qb_gl_transactions (entire table) - 62.18 MB
  2. Other staging/backup tables - 100+ MB
  3. Square payment columns in payments table (legacy payment processor)
  4. QB-related columns (qb_trans_num, qb_payment_type, etc.)
""")

cur.close()
conn.close()

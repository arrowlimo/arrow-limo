"""
Database Schema Optimization Report
Analyzes receipts table to identify columns for removal
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Connect
conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("RECEIPTS TABLE SCHEMA OPTIMIZATION REPORT")
print("=" * 100)
print()

# Get total row count
cur.execute("SELECT COUNT(*) FROM receipts")
total_rows = cur.fetchone()[0]
print(f"Total Receipts: {total_rows:,}")
print()

# Analyze each column
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts'
    ORDER BY ordinal_position
""")
columns = cur.fetchall()

empty_cols = []
sparse_cols = []
used_cols = []

print("COLUMN ANALYSIS")
print("-" * 100)
print(f"{'Column':<35} {'Type':<15} {'Non-NULL':<12} {'%':<8} {'Status':<15}")
print("-" * 100)

for col_name, col_type in columns:
    cur.execute(f"SELECT COUNT(*) FROM receipts WHERE {col_name} IS NOT NULL")
    non_null = cur.fetchone()[0]
    pct = (non_null / total_rows * 100) if total_rows > 0 else 0
    
    if pct == 0:
        status = "✗ EMPTY"
        empty_cols.append(col_name)
    elif pct < 5:
        status = "⚠ SPARSE"
        sparse_cols.append((col_name, pct))
    else:
        status = "✓ USED"
        used_cols.append((col_name, pct))
    
    print(f"{col_name:<35} {col_type:<15} {non_null:<12} {pct:>6.1f}% {status:<15}")

print()
print("=" * 100)
print(f"SUMMARY: {len(used_cols)} USED | {len(sparse_cols)} SPARSE | {len(empty_cols)} EMPTY")
print("=" * 100)
print()

print("✗ EMPTY COLUMNS (0% DATA - SAFE TO DROP):")
print("-" * 100)
for col in empty_cols:
    print(f"  • {col}")
print()
print(f"Migration SQL to drop empty columns:")
print("BEGIN TRANSACTION;")
for col in empty_cols:
    print(f"ALTER TABLE receipts DROP COLUMN {col};")
print("COMMIT;")
print()

print("⚠ SPARSE COLUMNS (1-20% DATA - REVIEW BEFORE DROPPING):")
print("-" * 100)
for col, pct in sorted(sparse_cols, key=lambda x: -x[1]):
    print(f"  • {col:<35} {pct:>6.1f}% ({int(pct * total_rows / 100):,} rows)")
print()

print("✓ USED COLUMNS (>20% DATA - KEEP ALL):")
print("-" * 100)
for col, pct in sorted(used_cols, key=lambda x: -x[1]):
    print(f"  • {col:<35} {pct:>6.1f}% ({int(pct * total_rows / 100):,} rows)")
print()

# Check for indexes on empty columns
print("=" * 100)
print("INDEXES ON EMPTY COLUMNS (should be removed):")
print("=" * 100)
for col in empty_cols:
    cur.execute(f"""
        SELECT indexname FROM pg_indexes 
        WHERE tablename='receipts' AND indexdef ILIKE '%{col}%'
    """)
    indexes = cur.fetchall()
    if indexes:
        for idx_name, in indexes:
            print(f"  DROP INDEX {idx_name};  -- on {col}")
print()

cur.close()
conn.close()

print("=" * 100)
print("RECOMMENDATION:")
print("=" * 100)
print(f"""
1. Drop {len(empty_cols)} completely empty columns
   - These columns have 0% data utilization
   - Safe to remove immediately
   - Will reduce table size and improve query performance

2. Review {len(sparse_cols)} sparse columns (1-20% usage)
   - Keep if business logic depends on them
   - Consider archiving to separate table if rarely used
   
3. Keep all {len(used_cols)} heavily-used columns (>20% usage)
   - Core to business reporting and analytics
""")
print("=" * 100)

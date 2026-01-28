"""
Data Type Audit - Verify data types match what's being stored
Checks for type mismatches, conversions, storage inefficiencies
"""
import os
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("DATA TYPE AUDIT - Checking Type Correctness")
print("=" * 80)

# 1. Check amounts - should be NUMERIC not TEXT
print("\n[1] AMOUNTS - Checking if stored as TEXT instead of NUMERIC...")
cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name IN ('gross_amount', 'amount', 'total_amount', 'payment_amount', 'charge_amount')
AND data_type IN ('character varying', 'text')
ORDER BY table_name
""")
text_amounts = cur.fetchall()
if text_amounts:
    print(f"⚠️ PROBLEM: {len(text_amounts)} amount columns stored as TEXT (inefficient):")
    for table, col, dtype in text_amounts[:10]:
        print(f"   {table}.{col} = {dtype}")
else:
    print("✅ All amounts stored as NUMERIC/DECIMAL")

# 2. Check IDs - should be INTEGER/BIGINT not VARCHAR
print("\n[2] IDs - Checking if stored as TEXT instead of INTEGER...")
cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE (column_name LIKE '%_id' OR column_name = 'id')
AND data_type IN ('character varying', 'text')
ORDER BY table_name
LIMIT 20
""")
text_ids = cur.fetchall()
if text_ids:
    print(f"⚠️ PROBLEM: {len(text_ids)} ID columns stored as TEXT:")
    for table, col, dtype in text_ids:
        print(f"   {table}.{col} = {dtype}")
else:
    print("✅ All IDs stored as INTEGER/BIGINT")

# 3. Check dates - should be DATE/TIMESTAMP not VARCHAR/TEXT
print("\n[3] DATES - Checking if stored as TEXT instead of DATE/TIMESTAMP...")
cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name IN ('date', 'transaction_date', 'created_at', 'updated_at', 
                      'receipt_date', 'posting_date', 'booking_date')
AND data_type IN ('character varying', 'text')
ORDER BY table_name
""")
text_dates = cur.fetchall()
if text_dates:
    print(f"⚠️ PROBLEM: {len(text_dates)} date columns stored as TEXT:")
    for table, col, dtype in text_dates[:10]:
        print(f"   {table}.{col} = {dtype}")
else:
    print("✅ All dates stored as DATE/TIMESTAMP")

# 4. Check booleans - should be BOOLEAN not INTEGER/TEXT
print("\n[4] BOOLEANS - Checking if stored as TEXT/INTEGER instead of BOOLEAN...")
cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name LIKE 'is_%'
AND data_type NOT IN ('boolean', 'bool')
ORDER BY table_name
LIMIT 20
""")
wrong_bools = cur.fetchall()
if wrong_bools:
    print(f"⚠️ PROBLEM: {len(wrong_bools)} boolean columns stored as wrong type:")
    for table, col, dtype in wrong_bools:
        print(f"   {table}.{col} = {dtype} (should be BOOLEAN)")
else:
    print("✅ All is_* columns stored as BOOLEAN")

# 5. Check for redundant storage (e.g., amount in cents AND amount in dollars)
print("\n[5] REDUNDANT COLUMNS - Looking for duplicate amount columns...")
redundant = defaultdict(list)
cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name LIKE '%amount%' OR column_name LIKE '%price%' OR column_name LIKE '%cost%'
ORDER BY table_name
""")
for table, col, dtype in cur.fetchall():
    if 'amount' in col.lower() or 'price' in col.lower() or 'cost' in col.lower():
        redundant[table].append(col)

print("Tables with multiple amount/price/cost columns:")
for table, cols in sorted(redundant.items()):
    if len(cols) > 1:
        print(f"  {table}: {cols}")

# 6. Check for encoding issues (UTF-8 needed for international text)
print("\n[6] TEXT COLUMNS - Checking for encoding/length issues...")
cur.execute("""
SELECT table_name, column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE data_type IN ('character varying', 'text', 'character')
AND table_name NOT LIKE '%backup%'
ORDER BY table_name
LIMIT 50
""")
text_cols = cur.fetchall()
print(f"Found {len(text_cols)} TEXT columns in active tables:")
for table, col, dtype, max_len in text_cols[:15]:
    size_info = f"(max {max_len})" if max_len else "(unlimited)"
    print(f"  {table}.{col} = {dtype} {size_info}")

# 7. Check numeric precision - are decimals stored correctly?
print("\n[7] NUMERIC PRECISION - Checking decimal storage...")
cur.execute("""
SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE data_type = 'numeric'
AND table_name IN ('receipts', 'payments', 'banking_transactions', 'charters')
ORDER BY table_name, column_name
""")
numerics = cur.fetchall()
print("Numeric columns in core tables:")
for table, col, dtype, precision, scale in numerics:
    print(f"  {table}.{col} = NUMERIC({precision},{scale})")
    if scale is None or scale < 2:
        print(f"    ⚠️ WARNING: scale={scale} (may lose cents precision)")

# 8. Check for NULL storage issues
print("\n[8] NULL HANDLING - Columns that should probably NOT NULL...")
cur.execute("""
SELECT table_name, column_name, is_nullable
FROM information_schema.columns
WHERE (column_name LIKE '%_id' OR 
       column_name LIKE 'amount%' OR
       column_name LIKE '%_date' OR
       column_name LIKE 'is_%')
AND is_nullable = 'YES'
AND table_name NOT LIKE '%backup%'
ORDER BY table_name
LIMIT 30
""")
nullable_keys = cur.fetchall()
print(f"Found {len(nullable_keys)} key/important columns that are nullable:")
for table, col, nullable in nullable_keys[:20]:
    print(f"  ⚠️ {table}.{col} is NULLABLE")

# 9. Type size analysis
print("\n[9] TYPE SIZE EFFICIENCY...")
cur.execute("""
SELECT 
    table_name,
    column_name,
    data_type,
    CASE 
        WHEN data_type = 'bigint' THEN '8 bytes'
        WHEN data_type = 'integer' THEN '4 bytes'
        WHEN data_type = 'smallint' THEN '2 bytes'
        WHEN data_type = 'numeric' THEN 'variable'
        WHEN data_type = 'text' THEN 'variable'
        WHEN data_type = 'character varying' THEN 'variable'
        WHEN data_type = 'boolean' THEN '1 byte'
        WHEN data_type = 'date' THEN '4 bytes'
        WHEN data_type = 'timestamp with time zone' THEN '8 bytes'
        ELSE 'unknown'
    END as size_per_row
FROM information_schema.columns
WHERE table_name IN ('receipts', 'payments', 'charters')
ORDER BY table_name
""")
print("Core table column sizes:")
for table, col, dtype, size in cur.fetchall()[:20]:
    print(f"  {table}.{col:30s} {dtype:20s} {size:10s}")

# 10. Check for mixed types in "type" or "status" columns
print("\n[10] STATUS/TYPE COLUMNS - Should use ENUM or FK, not TEXT...")
cur.execute("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE (column_name LIKE '%status%' OR column_name LIKE '%type%' OR column_name LIKE '%kind%')
AND data_type IN ('character varying', 'text')
AND table_name NOT LIKE '%backup%'
ORDER BY table_name
""")
enum_cols = cur.fetchall()
print(f"Found {len(enum_cols)} status/type columns stored as TEXT (should use ENUM):")
for table, col, dtype in enum_cols[:15]:
    # Sample values
    cur.execute(f"""
    SELECT DISTINCT {col} FROM {table}
    WHERE {col} IS NOT NULL
    LIMIT 5
    """)
    values = [str(row[0]) for row in cur.fetchall()]
    print(f"  {table}.{col}: {', '.join(values)}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("DATA TYPE AUDIT COMPLETE")
print("=" * 80)

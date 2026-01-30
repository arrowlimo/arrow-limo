import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Get columns from both tables
cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'lms_customers_enhanced'
ORDER BY ordinal_position
""")
enhanced_cols = {row[0]: row[1] for row in cur.fetchall()}

cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'clients'
ORDER BY ordinal_position
""")
clients_cols = {row[0]: row[1] for row in cur.fetchall()}

print("=" * 80)
print("lms_customers_enhanced COLUMNS")
print("=" * 80)
for col, dtype in sorted(enhanced_cols.items()):
    print(f"  {col:40} {dtype}")

print("\n" + "=" * 80)
print("clients COLUMNS")
print("=" * 80)
for col, dtype in sorted(clients_cols.items()):
    print(f"  {col:40} {dtype}")

print("\n" + "=" * 80)
print("UNIQUE TO lms_customers_enhanced (NOT in clients)")
print("=" * 80)
unique_enhanced = set(enhanced_cols.keys()) - set(clients_cols.keys())
if unique_enhanced:
    for col in sorted(unique_enhanced):
        print(f"  {col:40} {enhanced_cols[col]}")
else:
    print("  (NONE - all columns exist in clients)")

print("\n" + "=" * 80)
print("Record counts")
print("=" * 80)
cur.execute("SELECT COUNT(*) FROM lms_customers_enhanced")
enhanced_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM clients")
clients_count = cur.fetchone()[0]
print(f"  lms_customers_enhanced: {enhanced_count:,} records")
print(f"  clients: {clients_count:,} records")

# Check what customer_name_resolver view uses lms_customers_enhanced for
print("\n" + "=" * 80)
print("customer_name_resolver VIEW DEFINITION")
print("=" * 80)
cur.execute("""
SELECT view_definition
FROM information_schema.views
WHERE table_name = 'customer_name_resolver'
""")
result = cur.fetchone()
if result:
    print(result[0])
else:
    print("  (View not found)")

cur.close()
conn.close()

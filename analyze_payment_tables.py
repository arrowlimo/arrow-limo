import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("PAYMENT TABLES ANALYSIS")
print("="*80)
print()

# Find all tables with 'payment' in the name
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name ILIKE '%payment%'
    ORDER BY table_name
""")

payment_tables = [row[0] for row in cur.fetchall()]

print(f"Found {len(payment_tables)} payment-related tables:\n")

for table in payment_tables:
    # Get column info
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    
    print(f"{'─'*80}")
    print(f"TABLE: {table} ({row_count:,} rows)")
    print(f"{'─'*80}")
    
    for col in columns:
        nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
        print(f"  {col[0]:<30} {col[1]:<20} {nullable}")
    print()

print("\n" + "="*80)
print("PAYMENT FLOW ANALYSIS")
print("="*80)
print()

# Check which table is the main one
cur.execute("""
    SELECT tablename, indexname 
    FROM pg_indexes 
    WHERE tablename LIKE '%payment%'
    AND indexname LIKE '%primary%'
    ORDER BY tablename
""")

primary_keys = cur.fetchall()
print(f"Primary key tables: {len(primary_keys)}")
for pk in primary_keys:
    print(f"  - {pk[0]}")

print("\n" + "="*80)
print("FOREIGN KEY RELATIONSHIPS")
print("="*80)
print()

# Check FKs pointing to payment tables
for table in payment_tables:
    cur.execute(f"""
        SELECT 
            constraint_name, table_name, column_name, 
            referenced_table_name, referenced_column_name
        FROM information_schema.key_column_usage
        WHERE table_name = '{table}'
        AND referenced_table_name IS NOT NULL
        ORDER BY constraint_name
    """)
    
    fks = cur.fetchall()
    if fks:
        print(f"{table}:")
        for fk in fks:
            print(f"  {fk[1]}.{fk[2]} -> {fk[3]}.{fk[4]}")

cur.close()
conn.close()

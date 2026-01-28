#!/usr/bin/env python3
"""
Drop 6 empty payment-related tables identified during consolidation analysis.
Creates backup SQL first, then drops tables.
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# Tables to drop (all confirmed empty)
# Note: zero_payment_summary excluded - has 1 summary row from completed analysis
EMPTY_TABLES = [
    'banking_payment_links',
    'financing_payments',
    'multi_charter_payments',
    'payment_reconciliation_ledger',
    'square_loan_payments'
]

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
conn.autocommit = False
cur = conn.cursor()

print("="*80)
print("DROP EMPTY PAYMENT TABLES")
print("="*80)

# 1. Verify all tables are empty
print("\nVerifying tables are empty...")
print("-"*80)
all_empty = True
for table in EMPTY_TABLES:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table:<40} {count:>6} rows")
    if count > 0:
        all_empty = False
        print(f"    ❌ WARNING: {table} is NOT empty!")

if not all_empty:
    print("\n❌ ABORT: Some tables are not empty. Manual review required.")
    cur.close()
    conn.close()
    exit(1)

print("\n✅ All tables confirmed empty")

# 2. Generate backup SQL (CREATE TABLE statements)
backup_file = f"reports/empty_payment_tables_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
print(f"\nGenerating backup SQL: {backup_file}")
print("-"*80)

with open(backup_file, 'w') as f:
    f.write("-- Backup of empty payment tables structure\n")
    f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("-- Tables: " + ", ".join(EMPTY_TABLES) + "\n\n")
    
    for table in EMPTY_TABLES:
        cur.execute(f"""
            SELECT column_name, data_type, character_maximum_length, 
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        
        f.write(f"-- Table: {table}\n")
        f.write(f"CREATE TABLE {table} (\n")
        
        col_defs = []
        for col in columns:
            col_name, data_type, max_len, nullable, default = col
            col_def = f"  {col_name} {data_type}"
            if max_len:
                col_def += f"({max_len})"
            if nullable == 'NO':
                col_def += " NOT NULL"
            if default:
                col_def += f" DEFAULT {default}"
            col_defs.append(col_def)
        
        f.write(",\n".join(col_defs))
        f.write("\n);\n\n")

print(f"✅ Backup saved: {backup_file}")

# 3. Drop tables
print("\nDropping tables...")
print("-"*80)

try:
    for table in EMPTY_TABLES:
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print(f"  ✅ Dropped: {table}")
    
    conn.commit()
    print("\n✅ All tables dropped successfully")
    
    # 4. Verify
    print("\nVerification:")
    print("-"*80)
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = ANY(%s)
    """, (EMPTY_TABLES,))
    
    remaining = cur.fetchall()
    if remaining:
        print(f"  ❌ WARNING: {len(remaining)} tables still exist: {[r[0] for r in remaining]}")
    else:
        print(f"  ✅ All {len(EMPTY_TABLES)} tables successfully removed")

except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    print("Transaction rolled back")
finally:
    cur.close()
    conn.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Tables dropped: {len(EMPTY_TABLES)}")
print(f"Backup file: {backup_file}")
print("\nThese tables were empty and designed for functionality that was")
print("implemented differently (e.g., square_loan_payments vs square_capital_activity)")

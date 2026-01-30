import psycopg2
import json

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Tables to analyze for QB compatibility
key_tables = [
    'chart_of_accounts',
    'journal',
    'journal_lines',
    'general_ledger',
    'general_ledger_lines',
    'general_ledger_headers',
    'clients',
    'vendors',
    'invoices',
    'payables',
    'payments',
    'bank_accounts',
    'deposits'
]

for table in key_tables:
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print('='*60)
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema='public' AND table_name=%s
        )
    """, (table,))
    
    if not cur.fetchone()[0]:
        print("[FAIL] Table does not exist")
        continue
    
    # Get columns
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (table,))
    
    columns = cur.fetchall()
    print(f"\n✓ Table exists with {len(columns)} columns:\n")
    
    for col_name, dtype, max_len, nullable, default in columns:
        len_str = f"({max_len})" if max_len else ""
        null_str = "NULL" if nullable == 'YES' else "NOT NULL"
        default_str = f" DEFAULT {default}" if default else ""
        print(f"  {col_name:30} {dtype}{len_str:15} {null_str:10}{default_str}")
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"\n📊 Row count: {count:,}")
    
    # Sample a few rows if data exists
    if count > 0:
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        print(f"\n📋 Sample rows:")
        for i, row in enumerate(rows, 1):
            print(f"\n  Row {i}:")
            for col, val in zip(col_names, row):
                if val is not None:
                    val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                    print(f"    {col}: {val_str}")

conn.close()
print("\n" + "="*60)
print("Analysis complete")

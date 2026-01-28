import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

# Find staging/import tables
cur.execute("""
SELECT table_name, 
       (SELECT COUNT(*) FROM information_schema.columns c WHERE c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema='public' 
  AND (table_name LIKE '%staging%' OR table_name LIKE '%stage%' OR table_name LIKE '%temp%' OR table_name LIKE '%import%')
ORDER BY table_name
""")

staging_tables = cur.fetchall()

print("=" * 80)
print("STAGING/IMPORT TABLES IN DATABASE")
print("=" * 80)
print(f"\nFound {len(staging_tables)} staging/import tables:\n")

for table, col_count in staging_tables:
    # Get row count
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        print(f"  {table:<40} {row_count:>10,} rows  ({col_count} columns)")
    except Exception as e:
        print(f"  {table:<40} ERROR: {e}")

# Now get detailed stats for key staging tables
print("\n" + "=" * 80)
print("DETAILED STAGING TABLE ANALYSIS")
print("=" * 80)

staging_tables_of_interest = [
    'staging_driver_pay',
    'gl_transactions_staging', 
    'gl_staging',
    'gl_staging_corrected',
    'banking_import_staging',
    'receipt_staging'
]

for table in staging_tables_of_interest:
    # Check if table exists
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema='public' AND table_name = %s
        """, (table,))
        
        if cur.fetchone()[0] == 0:
            continue
        
        print(f"\n{table}:")
        print("-" * 80)
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total_rows = cur.fetchone()[0]
        print(f"Total rows: {total_rows:,}")
        
        # Get column list
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            LIMIT 10
        """, (table,))
        
        cols = cur.fetchall()
        print(f"Columns (first 10): {', '.join(c[0] for c in cols)}")
        
        # Try to get date range if there's a date column
        date_cols = ['txn_date', 'transaction_date', 'date', 'created_at', 'imported_at', 'pay_date']
        for date_col in date_cols:
            try:
                cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table} WHERE {date_col} IS NOT NULL")
                min_date, max_date = cur.fetchone()
                if min_date:
                    print(f"Date range ({date_col}): {min_date} to {max_date}")
                    break
            except:
                pass
        
        # Check for null/empty key fields
        if table == 'staging_driver_pay':
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE driver_id IS NULL OR driver_id = '') as null_driver_id,
                    COUNT(*) FILTER (WHERE gross_amount = 0 OR gross_amount IS NULL) as zero_gross,
                    COUNT(*) FILTER (WHERE net_amount = 0 OR net_amount IS NULL) as zero_net,
                    COUNT(DISTINCT file_id) as unique_files,
                    COUNT(DISTINCT driver_name) as unique_names
                FROM staging_driver_pay
            """)
            null_id, zero_gross, zero_net, files, names = cur.fetchone()
            print(f"NULL/empty driver_id: {null_id:,} ({null_id/total_rows*100:.1f}%)")
            print(f"Zero gross_amount: {zero_gross:,} ({zero_gross/total_rows*100:.1f}%)")
            print(f"Zero net_amount: {zero_net:,} ({zero_net/total_rows*100:.1f}%)")
            print(f"Unique file_ids: {files:,}")
            print(f"Unique driver_names: {names:,}")
    
    except Exception as e:
        print(f"\n{table}: ERROR - {e}")
        conn.rollback()
        continue

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
Staging tables requiring attention:

1. staging_driver_pay (262,884 rows):
   - 100% missing driver_id (needs name→ID mapping)
   - 100% zero monetary values (needs source file reprocessing)
   - Contains invalid dates (1969-12-31)
   - Action: Build fuzzy name matcher + reprocess source files

2. Other staging tables:
   - Check if they represent incomplete imports
   - Determine if they should be promoted to main tables
   - Archive or clean up if no longer needed
""")

cur.close()
conn.close()

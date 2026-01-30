import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 80)
print("JOURNAL TABLE ANALYSIS")
print("=" * 80)

# Check journal table structure and data
journal_tables = ['journal', 'journal_batches', 'journal_lines']

for table in journal_tables:
    print(f"\n📊 {table.upper()}")
    print("-" * 80)
    
    # Get columns
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    print(f"Columns ({len(columns)}):")
    for col, dtype in columns[:10]:
        print(f"  {col:30} {dtype}")
    if len(columns) > 10:
        print(f"  ... and {len(columns)-10} more")
    
    # Get record count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"\nTotal records: {count:,}")
    
    # Get date range if possible
    date_columns = [col for col, dtype in columns if 'date' in dtype.lower() or 'time' in dtype.lower()]
    if date_columns:
        date_col = date_columns[0]
        cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table} WHERE {date_col} IS NOT NULL")
        min_date, max_date = cur.fetchone()
        if min_date:
            print(f"Date range: {min_date} to {max_date}")
    
    # Sample 3 recent records
    if count > 0:
        print(f"\nSample records (3 most recent):")
        if date_columns:
            cur.execute(f"SELECT * FROM {table} ORDER BY {date_columns[0]} DESC LIMIT 3")
        else:
            cur.execute(f"SELECT * FROM {table} LIMIT 3")
        
        rows = cur.fetchall()
        for i, row in enumerate(rows):
            print(f"  Record {i+1}: {str(row)[:100]}...")

# Check if journal is actively used
print("\n" + "=" * 80)
print("JOURNAL USAGE ANALYSIS")
print("=" * 80)

# Check for recent activity (last 30 days)
# Note: Date column is TEXT, so we need to convert it
cur.execute("""
    SELECT COUNT(*) 
    FROM journal
    WHERE "Date" IS NOT NULL AND "Date" != ''
""")
total_with_date = cur.fetchone()[0]

if total_with_date > 0:
    print(f"\n⚠️ LEGACY TABLE - journal has {total_with_date:,} records but Date is TEXT type")
    print("   This appears to be QuickBooks import data, not active journal")
else:
    print(f"\n⚠️ INACTIVE - journal table has no valid dates")

# Check journal_batches recent activity
cur.execute("""
    SELECT 
        COUNT(*) as recent_batches,
        MIN(created_at) as oldest_recent,
        MAX(created_at) as newest_recent
    FROM journal_batches
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
""")
result = cur.fetchone()
if result[0] > 0:
    print(f"\n✅ journal_batches ACTIVE - {result[0]:,} batches in last 30 days")
else:
    cur.execute("SELECT MAX(created_at) FROM journal_batches")
    last_date = cur.fetchone()[0]
    if last_date:
        print(f"\n⚠️ journal_batches INACTIVE - Last batch: {last_date}")

cur.close()
conn.close()

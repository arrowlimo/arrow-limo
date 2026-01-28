"""
Find all accounting/ledger tables in the database.
Check for general ledger, journal entries, and other accounting tables.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 80)
print("ACCOUNTING/LEDGER TABLES IN DATABASE")
print("=" * 80)

# Search for accounting-related tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (
        table_name LIKE '%ledger%'
        OR table_name LIKE '%journal%'
        OR table_name LIKE '%accounting%'
        OR table_name LIKE '%gl_%'
        OR table_name LIKE 'general_%'
        OR table_name LIKE '%income%'
        OR table_name LIKE '%expense%'
        OR table_name LIKE '%revenue%'
    )
    ORDER BY table_name
""")

accounting_tables = [row[0] for row in cur.fetchall()]

if not accounting_tables:
    print("\n❌ NO ACCOUNTING TABLES FOUND")
else:
    print(f"\nFound {len(accounting_tables)} accounting-related tables:\n")
    
    for table_name in accounting_tables:
        # Get record count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        # Get date range if possible
        cur.execute(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            AND data_type IN ('date', 'timestamp without time zone', 'timestamp with time zone')
            ORDER BY ordinal_position
            LIMIT 1
        """)
        date_col = cur.fetchone()
        
        date_range = ""
        if date_col and count > 0:
            date_column = date_col[0]
            try:
                cur.execute(f"SELECT MIN({date_column}), MAX({date_column}) FROM {table_name}")
                min_date, max_date = cur.fetchone()
                if min_date and max_date:
                    date_range = f" | {min_date} to {max_date}"
            except:
                pass
        
        print(f"  📊 {table_name:50} {count:>8,} records{date_range}")
        
        # Show column names for each table
        cur.execute(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        print(f"      Columns: {', '.join(columns[:10])}")
        if len(columns) > 10:
            print(f"               {', '.join(columns[10:])}")
        print()

# Check specifically for year-based GL tables
print("=" * 80)
print("YEAR-BASED GENERAL LEDGER TABLES")
print("=" * 80)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND table_name ~ '^(gl|general_ledger)_[0-9]{4}$'
    ORDER BY table_name
""")

year_tables = [row[0] for row in cur.fetchall()]

if not year_tables:
    print("\n⚠️  No year-based GL tables found (e.g., gl_2024, general_ledger_2023)")
else:
    print(f"\nFound {len(year_tables)} year-based tables:\n")
    for table_name in year_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"  📅 {table_name:30} {count:>8,} records")

# Check for any chart of accounts
print("\n" + "=" * 80)
print("CHART OF ACCOUNTS / ACCOUNT TABLES")
print("=" * 80)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (
        table_name LIKE '%account%'
        AND table_name NOT LIKE '%bank%'
        AND table_name NOT LIKE '%customer%'
        AND table_name NOT LIKE '%client%'
    )
    ORDER BY table_name
""")

account_tables = [row[0] for row in cur.fetchall()]

if account_tables:
    print(f"\nFound {len(account_tables)} account-related tables:\n")
    for table_name in account_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"  📋 {table_name:50} {count:>8,} records")

cur.close()
conn.close()

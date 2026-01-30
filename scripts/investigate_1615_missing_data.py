#!/usr/bin/env python3
"""
Investigate missing 2012 transactions for CIBC 1615 account
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("INVESTIGATING CIBC 1615 ACCOUNT - 2012 TRANSACTIONS")
print("="*80)

# Check what we actually have in banking_transactions for 1615 in 2012
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '1615'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
    ORDER BY month
""")

print("\nBREAKDOWN BY MONTH for account 1615 in 2012:")
print(f"{'Month':<10} {'Count':<8} {'First Date':<15} {'Last Date':<15}")
print("-" * 60)

total_2012 = 0
for row in cur.fetchall():
    print(f"{row[0]:<10} {row[1]:<8} {str(row[2]):<15} {str(row[3]):<15}")
    total_2012 += row[1]

print("-" * 60)
print(f"TOTAL: {total_2012} transactions")

# Check ALL tables in the database for banking-related tables
print("\n" + "="*80)
print("SEARCHING FOR ALL BANKING-RELATED TABLES IN DATABASE")
print("="*80)

cur.execute("""
    SELECT table_name, 
           (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
    FROM information_schema.tables t
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
      AND (
          table_name LIKE '%bank%' OR
          table_name LIKE '%transaction%' OR
          table_name LIKE '%cibc%' OR
          table_name LIKE '%scotia%' OR
          table_name LIKE '%statement%'
      )
    ORDER BY table_name
""")

banking_tables = cur.fetchall()
print(f"\nFound {len(banking_tables)} banking-related tables:")
for table in banking_tables:
    print(f"  - {table[0]} ({table[1]} columns)")

# Check if there are any staging or import tables
print("\n" + "="*80)
print("CHECKING FOR STAGING/IMPORT TABLES")
print("="*80)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
      AND (
          table_name LIKE '%staging%' OR
          table_name LIKE '%import%' OR
          table_name LIKE '%raw%' OR
          table_name LIKE '%temp%'
      )
    ORDER BY table_name
""")

staging_tables = cur.fetchall()
if staging_tables:
    print(f"\nFound {len(staging_tables)} staging/import tables:")
    for table in staging_tables:
        print(f"  - {table[0]}")
else:
    print("\nNo staging/import tables found")

# Check for any tables with "1615" data
print("\n" + "="*80)
print("SEARCHING FOR ACCOUNT 1615 IN ALL TABLES")
print("="*80)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

all_tables = [row[0] for row in cur.fetchall()]

for table_name in all_tables:
    # Check if table has account_number column
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name IN ('account_number', 'account', 'bank_account', 'account_id')
    """, (table_name,))
    
    account_columns = [row[0] for row in cur.fetchall()]
    
    if account_columns:
        for col in account_columns:
            try:
                cur.execute(f"""
                    SELECT COUNT(*)
                    FROM {table_name}
                    WHERE {col}::text LIKE '%1615%'
                """)
                count = cur.fetchone()[0]
                if count > 0:
                    print(f"✓ Found {count} rows in table '{table_name}' (column: {col})")
            except Exception as e:
                pass  # Skip tables with errors

# Check source files in banking_transactions
print("\n" + "="*80)
print("SOURCE FILES FOR ACCOUNT 1615")
print("="*80)

cur.execute("""
    SELECT 
        source_file,
        import_batch,
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY source_file, import_batch, EXTRACT(YEAR FROM transaction_date)
    ORDER BY year, source_file
""")

print(f"\n{'Source File':<50} {'Import Batch':<30} {'Year':<6} {'Count':<8}")
print("-" * 100)
for row in cur.fetchall():
    print(f"{(row[0] or 'NULL'):<50} {(row[1] or 'NULL'):<30} {int(row[2]):<6} {row[3]:<8}")

cur.close()
conn.close()

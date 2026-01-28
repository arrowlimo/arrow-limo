#!/usr/bin/env python3
"""
Analyze CIBC staging tables (7,759 total rows).
- cibc_checking_staging (6,506 rows)
- cibc_ledger_staging (53 rows)
- cibc_qbo_staging (1,200 rows)
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("CIBC STAGING TABLES ANALYSIS")
print("=" * 80)

# Check which tables exist
tables = ['cibc_checking_staging', 'cibc_ledger_staging', 'cibc_qbo_staging']
existing_tables = []

for table in tables:
    cur.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}')")
    if cur.fetchone()[0]:
        existing_tables.append(table)

print(f"\nExisting tables: {len(existing_tables)}")
for table in existing_tables:
    print(f"  - {table}")

if not existing_tables:
    print("\nNo CIBC staging tables found!")
    cur.close()
    conn.close()
    exit(0)

# Analyze each table
for table in existing_tables:
    print("\n" + "=" * 80)
    print(f"{table.upper()}")
    print("=" * 80)
    
    # Row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    print(f"\nTotal rows: {row_count:,}")
    
    # Schema
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    
    print(f"\nColumns ({cur.rowcount}):")
    columns = []
    for col_name, col_type in cur.fetchall():
        columns.append(col_name)
        print(f"  {col_name:30} {col_type}")
    
    # Check for date columns
    date_cols = [c for c in columns if 'date' in c.lower()]
    amount_cols = [c for c in columns if 'amount' in c.lower() or 'debit' in c.lower() or 'credit' in c.lower()]
    
    if date_cols and amount_cols:
        date_col = date_cols[0]
        
        # Date range and amounts
        if amount_cols:
            # Try to find debit/credit or single amount
            debit_col = next((c for c in amount_cols if 'debit' in c.lower()), None)
            credit_col = next((c for c in amount_cols if 'credit' in c.lower()), None)
            
            if debit_col and credit_col:
                cur.execute(f"""
                    SELECT 
                        MIN({date_col}) as min_date,
                        MAX({date_col}) as max_date,
                        SUM(COALESCE({debit_col}, 0)) as total_debits,
                        SUM(COALESCE({credit_col}, 0)) as total_credits
                    FROM {table}
                    WHERE {date_col} IS NOT NULL
                """)
                stats = cur.fetchone()
                print(f"\nDate range: {stats[0]} to {stats[1]}")
                print(f"Total debits: ${stats[2]:,.2f}")
                print(f"Total credits: ${stats[3]:,.2f}")
            else:
                amount_col = amount_cols[0]
                cur.execute(f"""
                    SELECT 
                        MIN({date_col}) as min_date,
                        MAX({date_col}) as max_date,
                        SUM(COALESCE({amount_col}, 0)) as total_amount
                    FROM {table}
                    WHERE {date_col} IS NOT NULL
                """)
                stats = cur.fetchone()
                print(f"\nDate range: {stats[0]} to {stats[1]}")
                print(f"Total amount: ${stats[2]:,.2f}")
        
        # Sample data
        print(f"\nSample data (first 5 rows):")
        cur.execute(f"SELECT * FROM {table} LIMIT 5")
        rows = cur.fetchall()
        for row in rows:
            print(f"  {row[:5]}")  # First 5 columns only

# Compare with banking_transactions
print("\n" + "=" * 80)
print("COMPARISON WITH BANKING_TRANSACTIONS")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as rows,
        MIN(transaction_date) as min_date,
        MAX(transaction_date) as max_date,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits
    FROM banking_transactions
    WHERE account_number LIKE '%CIBC%' OR account_number LIKE '%0228362%'
""")

bt_stats = cur.fetchone()
print(f"\nCIBC transactions in banking_transactions:")
print(f"  Rows: {bt_stats[0]:,}")
print(f"  Date range: {bt_stats[1]} to {bt_stats[2]}")
print(f"  Total debits: ${bt_stats[3]:,.2f}")
print(f"  Total credits: ${bt_stats[4]:,.2f}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
Based on staging table analysis:

1. Check date overlap with banking_transactions
2. Look for gaps in banking data that staging might fill
3. Determine if staging data is:
   - DUPLICATES of existing banking_transactions
   - NEW data that should be promoted
   - OLDER data for historical completeness

4. Action options:
   A. If duplicates → ARCHIVE staging tables
   B. If new data → PROMOTE to banking_transactions
   C. If gaps → SELECTIVE PROMOTION
""")

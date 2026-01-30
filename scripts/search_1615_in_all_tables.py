#!/usr/bin/env python3
"""
Search for account 1615 data in ALL tables (general_ledger, etc.)
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("SEARCHING ALL TABLES FOR ACCOUNT 1615 DATA")
print("="*80)

# Check general_ledger table
print("\n1. GENERAL_LEDGER TABLE")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM general_ledger
    WHERE account LIKE '%1615%'
""")

result = cur.fetchone()
if result[0] > 0:
    print(f"✅ Found {result[0]:,} entries with '1615' in account field")
    print(f"   Date range: {result[1]} to {result[2]}")
    
    # Get year breakdown (handle NULL dates)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as count,
            SUM(debit) as total_debits,
            SUM(credit) as total_credits
        FROM general_ledger
        WHERE account LIKE '%1615%'
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year NULLS FIRST
    """)
    
    print(f"\n   {'Year':<6} {'Count':<10} {'Debits':<15} {'Credits':<15}")
    print(f"   {'-'*50}")
    
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else None
        count = row[1]
        debits = float(row[2] or 0)
        credits = float(row[3] or 0)
        year_str = str(year) if year else "NULL"
        print(f"   {year_str:<6} {count:<10} ${debits:>13,.2f} ${credits:>13,.2f}")
    
    # Show sample transactions
    print("\n   Sample transactions:")
    cur.execute("""
        SELECT transaction_date, account, description, debit, credit
        FROM general_ledger
        WHERE account LIKE '%1615%'
        ORDER BY transaction_date
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        debit = f"${row[3]:,.2f}" if row[3] else ""
        credit = f"${row[4]:,.2f}" if row[4] else ""
        print(f"   {row[0]} | {row[1]:<30} | {row[2][:30]:<30} | D:{debit:>10} C:{credit:>10}")
else:
    print("❌ No entries found in general_ledger")

# Check gl_transactions table
print("\n2. GL_TRANSACTIONS TABLE")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_name = 'gl_transactions'
""")

if cur.fetchone()[0] > 0:
    cur.execute("""
        SELECT COUNT(*)
        FROM gl_transactions
        WHERE account_number LIKE '%1615%' OR account_name LIKE '%1615%'
    """)
    
    count = cur.fetchone()[0]
    if count > 0:
        print(f"✅ Found {count:,} entries")
    else:
        print("❌ No entries found")
else:
    print("⚠️  Table gl_transactions does not exist")

# Check bank_transactions_staging
print("\n3. BANK_TRANSACTIONS_STAGING TABLE")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_name = 'bank_transactions_staging'
""")

if cur.fetchone()[0] > 0:
    cur.execute("""
        SELECT COUNT(*)
        FROM bank_transactions_staging
        WHERE account_number LIKE '%1615%'
    """)
    
    count = cur.fetchone()[0]
    if count > 0:
        print(f"✅ Found {count:,} entries")
    else:
        print("❌ No entries found")
else:
    print("⚠️  Table bank_transactions_staging does not exist")

# Check cibc_accounts table
print("\n4. CIBC_ACCOUNTS TABLE")
print("-" * 80)

cur.execute("""
    SELECT * FROM cibc_accounts
    WHERE account_number LIKE '%1615%'
""")

rows = cur.fetchall()
if rows:
    print(f"✅ Found {len(rows)} CIBC account entries:")
    for row in rows:
        print(f"   {row}")
else:
    print("❌ No entries found")

# Search all tables for 1615 patterns
print("\n5. COMPREHENSIVE SEARCH ACROSS ALL TABLES")
print("-" * 80)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

all_tables = [row[0] for row in cur.fetchall()]

found_in_tables = []

for table in all_tables:
    # Check if table has account-related columns
    cur.execute(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{table}'
          AND (column_name LIKE '%account%' OR column_name = 'description')
        LIMIT 1
    """)
    
    if cur.fetchone():
        try:
            # Try to find 1615 references
            cur.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE CAST(COALESCE(
                    account_number,
                    account,
                    account_name,
                    description,
                    ''
                ) AS TEXT) LIKE '%1615%'
            """)
            
            count = cur.fetchone()[0]
            if count > 0:
                found_in_tables.append((table, count))
        except:
            pass

if found_in_tables:
    print(f"\nFound '1615' references in {len(found_in_tables)} additional tables:")
    for table, count in found_in_tables:
        print(f"  • {table}: {count:,} rows")
else:
    print("\n❌ No additional tables with 1615 data found")

cur.close()
conn.close()

print("\n" + "="*80)
print("Next: If data found in general_ledger, import it to banking_transactions")
print("="*80)

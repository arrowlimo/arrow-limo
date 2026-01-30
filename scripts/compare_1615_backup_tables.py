#!/usr/bin/env python3
"""
Compare 1615 backup tables vs main banking_transactions table
"""

import psycopg2
import pandas as pd

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

print("="*80)
print("COMPARING ACCOUNT 1615 - MAIN TABLE VS BACKUP TABLES")
print("="*80)

# Check main table
query_main = """
    SELECT 
        transaction_date as date,
        description,
        debit_amount as debit,
        credit_amount as credit,
        source_file,
        'MAIN' as source_table
    FROM banking_transactions
    WHERE account_number = '1615'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
"""

df_main = pd.read_sql_query(query_main, conn)

# Check backup table
query_backup = """
    SELECT 
        transaction_date as date,
        description,
        debit_amount as debit,
        credit_amount as credit,
        source_file,
        'BACKUP_2012' as source_table
    FROM banking_transactions_1615_backup_2012
    WHERE account_number = '1615'
    ORDER BY transaction_date
"""

df_backup = pd.read_sql_query(query_backup, conn)

print(f"\nMAIN TABLE: {len(df_main)} transactions in 2012")
print(f"BACKUP TABLE: {len(df_backup)} transactions")

# Show breakdown by month
print("\n" + "="*80)
print("MAIN TABLE - MONTHLY BREAKDOWN:")
print("="*80)
print(df_main.groupby(df_main['date'].dt.to_period('M')).size())

if len(df_backup) > 0:
    print("\n" + "="*80)
    print("BACKUP TABLE - MONTHLY BREAKDOWN:")
    print("="*80)
    print(df_backup.groupby(df_backup['date'].dt.to_period('M')).size())
    
    print("\n" + "="*80)
    print("BACKUP TABLE - ALL TRANSACTIONS:")
    print("="*80)
    print(df_backup.to_string(index=False))

# Check if there are transactions in backup that aren't in main
print("\n" + "="*80)
print("FINDING TRANSACTIONS IN BACKUP BUT NOT IN MAIN")
print("="*80)

# Create signatures
df_main['sig'] = (df_main['date'].dt.strftime('%Y-%m-%d') + '|' + 
                  df_main['description'].astype(str) + '|' +
                  df_main['debit'].fillna(0).astype(str) + '|' +
                  df_main['credit'].fillna(0).astype(str))

df_backup['sig'] = (df_backup['date'].dt.strftime('%Y-%m-%d') + '|' + 
                    df_backup['description'].astype(str) + '|' +
                    df_backup['debit'].fillna(0).astype(str) + '|' +
                    df_backup['credit'].fillna(0).astype(str))

main_sigs = set(df_main['sig'])
backup_sigs = set(df_backup['sig'])

missing_in_main = backup_sigs - main_sigs

if missing_in_main:
    print(f"\n❌ Found {len(missing_in_main)} transactions in BACKUP that are MISSING from MAIN table:")
    for sig in missing_in_main:
        row = df_backup[df_backup['sig'] == sig].iloc[0]
        print(f"  {row['date']} | {row['description']:<40} | Debit: ${row['debit'] or 0:.2f} | Credit: ${row['credit'] or 0:.2f}")
else:
    print("\n✅ All backup transactions are in main table")

# Also check other years
print("\n" + "="*80)
print("CHECKING OTHER 1615 BACKUP TABLES")
print("="*80)

for year in [2013, 2014, 2015, 2016, 2017]:
    cur = conn.cursor()
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM banking_transactions_1615_backup_{year}
        WHERE account_number = '1615'
    """)
    backup_count = cur.fetchone()[0]
    
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM banking_transactions
        WHERE account_number = '1615'
          AND EXTRACT(YEAR FROM transaction_date) = {year}
    """)
    main_count = cur.fetchone()[0]
    
    status = "✅" if backup_count == main_count else "❌"
    print(f"{status} {year}: Main={main_count}, Backup={backup_count}")
    cur.close()

conn.close()

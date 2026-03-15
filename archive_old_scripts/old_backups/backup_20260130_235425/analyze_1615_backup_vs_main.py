#!/usr/bin/env python3
"""
Check what's in the 1615 backup tables vs main table to understand the data loss pattern
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("CIBC 1615 BACKUP TABLES - DETAILED ANALYSIS")
print("="*80)

# Check each backup table
for year in [2012, 2013, 2014, 2015, 2016, 2017]:
    backup_table = f"banking_transactions_1615_backup_{year}"
    
    print(f"\n{'='*80}")
    print(f"{backup_table}")
    print(f"{'='*80}")
    
    # Check if backup exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = %s
    """, (backup_table,))
    
    if cur.fetchone()[0] == 0:
        print(f"❌ Backup table does not exist")
        continue
    
    # Get backup data summary
    cur.execute(f"""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM {backup_table}
        WHERE account_number = '1615'
    """)
    
    backup_data = cur.fetchone()
    
    # Get main table data for same year
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE account_number = '1615'
          AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    main_data = cur.fetchone()
    
    print(f"\nBACKUP TABLE:")
    print(f"  Count: {backup_data[0]}")
    print(f"  Date Range: {backup_data[1]} to {backup_data[2]}")
    print(f"  Debits: ${float(backup_data[3] or 0):,.2f}")
    print(f"  Credits: ${float(backup_data[4] or 0):,.2f}")
    
    print(f"\nMAIN TABLE ({year}):")
    print(f"  Count: {main_data[0]}")
    print(f"  Date Range: {main_data[1]} to {main_data[2]}")
    print(f"  Debits: ${float(main_data[3] or 0):,.2f}")
    print(f"  Credits: ${float(main_data[4] or 0):,.2f}")
    
    diff = backup_data[0] - main_data[0]
    if diff != 0:
        print(f"\n⚠️  DIFFERENCE: {diff} transactions in backup NOT in main table!")
    else:
        print(f"\n✅ Same transaction count")

# Now specifically check 2012 April-December
print(f"\n{'='*80}")
print("2012 DETAILED BREAKDOWN - WHERE IS APR-DEC DATA?")
print(f"{'='*80}")

for month in range(1, 13):
    # Backup table
    cur.execute(f"""
        SELECT COUNT(*)
        FROM banking_transactions_1615_backup_2012
        WHERE account_number = '1615'
          AND EXTRACT(MONTH FROM transaction_date) = {month}
    """)
    backup_count = cur.fetchone()[0]
    
    # Main table
    cur.execute(f"""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE account_number = '1615'
          AND EXTRACT(YEAR FROM transaction_date) = 2012
          AND EXTRACT(MONTH FROM transaction_date) = {month}
    """)
    main_count = cur.fetchone()[0]
    
    status = "❌" if backup_count != main_count else "✅"
    print(f"{status} Month {month:02d}: Backup={backup_count:3d}, Main={main_count:3d}, Diff={backup_count - main_count:3d}")

cur.close()
conn.close()

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
print("If backup tables have more data than main table,")
print("run: python scripts/restore_from_backups.py")
print("This will restore ALL data from backup tables to main table.")

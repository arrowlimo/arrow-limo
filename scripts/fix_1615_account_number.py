#!/usr/bin/env python3
"""
Fix account 1615 -> Move all transactions to 0228362 (the correct CIBC account)
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("FIXING ACCOUNT 1615 -> MOVING TO 0228362")
print("="*80)

# Create backup first
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_table = f'banking_transactions_1615_fix_backup_{timestamp}'

print(f"\n1. Creating backup: {backup_table}")
cur.execute(f"""
    CREATE TABLE {backup_table} AS
    SELECT * FROM banking_transactions
    WHERE account_number = '1615'
""")

cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]
print(f"   ✅ Backed up {backup_count} transactions")

# Get current counts
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615'")
count_1615_before = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '0228362'")
count_0228362_before = cur.fetchone()[0]

print(f"\n2. Current counts:")
print(f"   Account 1615: {count_1615_before}")
print(f"   Account 0228362: {count_0228362_before}")

# Update all 1615 transactions to 0228362
print(f"\n3. Updating account_number from '1615' to '0228362'...")
cur.execute("""
    UPDATE banking_transactions
    SET account_number = '0228362'
    WHERE account_number = '1615'
""")

updated_count = cur.rowcount
print(f"   ✅ Updated {updated_count} transactions")

# Commit the changes
conn.commit()
print(f"\n4. ✅ Changes committed to database")

# Verify final counts
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615'")
count_1615_after = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '0228362'")
count_0228362_after = cur.fetchone()[0]

print(f"\n5. Final counts:")
print(f"   Account 1615: {count_1615_after} (should be 0)")
print(f"   Account 0228362: {count_0228362_after} (was {count_0228362_before})")
print(f"   Increase: +{count_0228362_after - count_0228362_before}")

# Verify by year
print(f"\n6. Breakdown by year for account 0228362:")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '0228362'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

print(f"   {'Year':<6} {'Count':<10}")
print(f"   {'-'*20}")
for row in cur.fetchall():
    print(f"   {int(row[0]):<6} {row[1]:<10}")

print("\n" + "="*80)
print("✅ COMPLETE - Account 1615 transactions moved to 0228362")
print("="*80)
print(f"\nBackup table: {backup_table}")
print("To rollback: UPDATE banking_transactions SET account_number = '1615' ")
print(f"             WHERE transaction_id IN (SELECT transaction_id FROM {backup_table})")

cur.close()
conn.close()

#!/usr/bin/env python3
"""
EMERGENCY ROLLBACK - Restore account 1615 transactions
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("EMERGENCY ROLLBACK - RESTORING ACCOUNT 1615")
print("="*80)

backup_table = 'banking_transactions_1615_fix_backup_20251216_101115'

# Verify backup exists
cur.execute(f"""
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_name = '{backup_table}'
""")

if cur.fetchone()[0] == 0:
    print(f"❌ ERROR: Backup table {backup_table} not found!")
    conn.close()
    exit(1)

# Get transaction IDs from backup
cur.execute(f"SELECT transaction_id FROM {backup_table}")
backup_ids = [row[0] for row in cur.fetchall()]

print(f"\n1. Found backup with {len(backup_ids)} transactions")

# Restore account number to 1615
print(f"\n2. Restoring account_number back to '1615'...")
cur.execute(f"""
    UPDATE banking_transactions
    SET account_number = '1615'
    WHERE transaction_id IN (
        SELECT transaction_id FROM {backup_table}
    )
""")

restored_count = cur.rowcount
print(f"   ✅ Restored {restored_count} transactions")

conn.commit()
print(f"\n3. ✅ Changes committed")

# Verify restoration
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615'")
count_1615 = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '0228362'")
count_0228362 = cur.fetchone()[0]

print(f"\n4. Final counts:")
print(f"   Account 1615: {count_1615}")
print(f"   Account 0228362: {count_0228362}")

print("\n" + "="*80)
print("✅ ROLLBACK COMPLETE - Account 1615 restored")
print("="*80)

cur.close()
conn.close()

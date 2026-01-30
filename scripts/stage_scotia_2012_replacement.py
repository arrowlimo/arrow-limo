#!/usr/bin/env python3
"""
Stage manually verified Scotia Bank 2012 transactions for database replacement.
This will backup existing data and prepare for clean import.
"""

import psycopg2
from datetime import datetime
import csv

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("=" * 80)
print("SCOTIA BANK 2012 DATA REPLACEMENT - STAGING PROCESS")
print("=" * 80)

# Step 1: Backup existing Scotia Bank 2012 data
print("\n[STEP 1] Creating backup of existing Scotia Bank 2012 data...")

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
      AND transaction_date >= '2012-01-01' 
      AND transaction_date <= '2012-12-31'
""")
existing_count = cur.fetchone()[0]
print(f"  Found {existing_count} existing transactions to backup")

# Create backup table
backup_table = f"scotia_2012_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
cur.execute(f"""
    CREATE TABLE {backup_table} AS 
    SELECT * FROM banking_transactions 
    WHERE account_number = '903990106011' 
      AND transaction_date >= '2012-01-01' 
      AND transaction_date <= '2012-12-31'
""")
conn.commit()
print(f"  ✓ Backup created: {backup_table}")

# Step 2: Export existing transaction IDs for reference
print("\n[STEP 2] Exporting existing transaction ID mappings...")
cur.execute(f"""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM {backup_table}
    ORDER BY transaction_date, transaction_id
""")
backup_data = cur.fetchall()

with open('reports/scotia_2012_backup_ids.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['transaction_id', 'transaction_date', 'description', 'debit_amount', 'credit_amount'])
    writer.writerows(backup_data)
print(f"  ✓ Backup IDs exported to: reports/scotia_2012_backup_ids.csv")

# Step 3: Analyze ID ranges
print("\n[STEP 3] Analyzing transaction ID ranges...")
cur.execute(f"""
    SELECT 
        MIN(transaction_id) as min_id,
        MAX(transaction_id) as max_id,
        COUNT(DISTINCT transaction_id) as distinct_ids
    FROM {backup_table}
""")
min_id, max_id, distinct_ids = cur.fetchone()
print(f"  ID Range: {min_id} to {max_id}")
print(f"  Distinct IDs: {distinct_ids}")
print(f"  Gap Check: {max_id - min_id + 1 - distinct_ids} gaps in sequence")

# Step 4: Check for overlapping IDs in other accounts
print("\n[STEP 4] Checking for ID conflicts with other accounts...")
cur.execute(f"""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE transaction_id >= {min_id} 
      AND transaction_id <= {max_id}
      AND account_number != '903990106011'
""")
conflicts = cur.fetchone()[0]
if conflicts > 0:
    print(f"  [WARN]  WARNING: {conflicts} transactions from other accounts use IDs in Scotia range")
    print(f"  These IDs will need to be preserved or remapped")
else:
    print(f"  ✓ No ID conflicts detected")

# Step 5: Prepare staging instructions
print("\n[STEP 5] Staging instructions prepared:")
print(f"""
  Next steps:
  1. Delete existing Scotia 2012 data:
     DELETE FROM banking_transactions 
     WHERE account_number = '903990106011' 
       AND transaction_date >= '2012-01-01' 
       AND transaction_date <= '2012-12-31'
  
  2. Import manually verified data from your spreadsheet
  
  3. If needed, restore from backup:
     INSERT INTO banking_transactions 
     SELECT * FROM {backup_table}
""")

# Step 6: Generate cleanup script
print("\n[STEP 6] Generating cleanup and import scripts...")

with open('scripts/delete_scotia_2012.sql', 'w') as f:
    f.write(f"""-- Delete existing Scotia Bank 2012 data
-- Backup table: {backup_table}
-- Generated: {datetime.now()}

BEGIN;

DELETE FROM banking_transactions 
WHERE account_number = '903990106011' 
  AND transaction_date >= '2012-01-01' 
  AND transaction_date <= '2012-12-31';

-- Check deletion
SELECT 'Deleted ' || ROW_COUNT() || ' rows' as result;

-- Rollback if you want to undo (comment out COMMIT, uncomment ROLLBACK):
COMMIT;
-- ROLLBACK;
""")
print(f"  ✓ SQL deletion script: scripts/delete_scotia_2012.sql")

with open('scripts/restore_scotia_2012_backup.sql', 'w') as f:
    f.write(f"""-- Restore Scotia Bank 2012 from backup
-- Backup table: {backup_table}
-- Generated: {datetime.now()}

BEGIN;

-- First delete current data
DELETE FROM banking_transactions 
WHERE account_number = '903990106011' 
  AND transaction_date >= '2012-01-01' 
  AND transaction_date <= '2012-12-31';

-- Restore from backup
INSERT INTO banking_transactions 
SELECT * FROM {backup_table};

-- Check restoration
SELECT 'Restored ' || COUNT(*) || ' rows' as result
FROM banking_transactions 
WHERE account_number = '903990106011' 
  AND transaction_date >= '2012-01-01' 
  AND transaction_date <= '2012-12-31';

COMMIT;
""")
print(f"  ✓ SQL restoration script: scripts/restore_scotia_2012_backup.sql")

print("\n" + "=" * 80)
print("STAGING COMPLETE")
print("=" * 80)
print(f"""
Summary:
- Backup table: {backup_table}
- Existing records: {existing_count}
- Backup IDs saved: reports/scotia_2012_backup_ids.csv
- Ready for manual data import

IMPORTANT: Do not delete {backup_table} until you verify the new data!
""")

cur.close()
conn.close()

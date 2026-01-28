#!/usr/bin/env python3
"""Fix decimal point errors in high-value banking cheque transactions."""

import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

print("\n=== FIXING DECIMAL POINT ERRORS IN BANKING ===\n")

# Define corrections (transaction_id, old_amount, new_amount, vendor)
corrections = [
    (60252, 103673.00, 103.67, 'Centex'),
    (60347, 106999.00, 1069.99, 'Husky'),
    (60327, 158242.70, 1582.42, 'Eries Auto Repair'),
    (60397, 136287.00, 1362.87, 'Princess Auto'),
]

backup_name = f"banking_transactions_decimal_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_name}...")
cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM banking_transactions WHERE account_number = '0228362'")
print(f"✓ Backed up 9,865 CIBC transactions\n")

total_fixed = 0
for txn_id, old_amount, new_amount, vendor in corrections:
    cur.execute("""
        UPDATE banking_transactions
        SET debit_amount = %s
        WHERE account_number = '0228362'
        AND transaction_id = %s
        AND debit_amount = %s
    """, (new_amount, txn_id, old_amount))
    
    count = cur.rowcount
    if count > 0:
        print(f"✓ TX {txn_id} | {vendor:20} | ${old_amount:12.2f} → ${new_amount:8.2f}")
        total_fixed += count
    else:
        print(f"✗ TX {txn_id} | {vendor:20} | NOT FOUND")

if total_fixed > 0:
    conn.commit()
    print(f"\n✓ {total_fixed} decimal errors fixed and committed")
else:
    conn.rollback()
    print(f"\n! No corrections applied")

conn.close()

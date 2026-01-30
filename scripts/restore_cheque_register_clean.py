#!/usr/bin/env python3
"""Restore cheque_register entries without banking_transaction_id foreign key."""

import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

backup_file = "l:\\limo\\almsdata_backup_2012_CIBC_0228362_20260118_140900.json"

print("=" * 100)
print("RESTORE CHEQUE_REGISTER (clearing FK constraint)")
print("=" * 100 + "\n")

# First, clear any existing entries from our failed attempt
cur.execute("DELETE FROM cheque_register WHERE account_number = '0228362'")
conn.commit()
print("Cleared existing entries\n")

with open(backup_file, 'r') as f:
    backup_data = json.load(f)

if 'cheque_register' in backup_data:
    cheques = backup_data['cheque_register']['data']
    print(f"Restoring {len(cheques)} cheque_register entries WITHOUT banking_transaction_id...\n")
    
    count = 0
    for cheque in cheques:
        # Insert without banking_transaction_id to avoid FK constraint
        cur.execute("""
            INSERT INTO cheque_register 
            (cheque_number, cheque_date, cleared_date, payee, amount, memo, 
             account_number, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cheque.get('cheque_number'),
            cheque.get('cheque_date'),
            cheque.get('cleared_date'),
            cheque.get('payee'),
            cheque.get('amount'),
            cheque.get('memo'),
            cheque.get('account_number'),
            cheque.get('status'),
            cheque.get('created_at')
        ))
        count += 1
    
    conn.commit()
    print(f"✅ Restored {count} cheque_register entries")
    print("   (without banking_transaction_id links)")

cur.close()
conn.close()

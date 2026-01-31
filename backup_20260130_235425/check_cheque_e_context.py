#!/usr/bin/env python3
"""Investigate the cheque transactions - check if we have more context."""

import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Search backup table for similar cheque patterns around the same date
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        ROUND(debit_amount::numeric, 2) as debit,
        ROUND(credit_amount::numeric, 2) as credit
    FROM banking_transactions_typo_fix_20251206_230713
    WHERE transaction_date BETWEEN '2012-08-01' AND '2012-08-05'
    ORDER BY transaction_date, transaction_id;
""")

print("\n=== TRANSACTIONS AROUND TX 60356 (Aug 2-5, 2012) ===\n")
for row in cur.fetchall():
    txn_id, date, desc, debit, credit = row
    debit_str = f"${debit:8.2f}" if debit else "          "
    credit_str = f"${credit:8.2f}" if credit else "          "
    print(f"TX {txn_id:5} | {date} | {desc:50} | Debit: {debit_str} | Credit: {credit_str}")

conn.close()

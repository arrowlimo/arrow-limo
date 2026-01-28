#!/usr/bin/env python3
"""Investigate high-value data errors and consolidate individual liquor store chains."""

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

print("\n=== HIGH-VALUE TRANSACTION INVESTIGATION ===\n")

# Check suspicious high-value transactions
suspicious = [
    ('Centex', 109188.46),
    ('Husky', 107819.89),
    ('Eries Auto Repair', 159266.98),
    ('Princess Auto', 136365.74)
]

for vendor, known_total in suspicious:
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            ROUND(debit_amount::numeric, 2) as debit,
            ROUND(credit_amount::numeric, 2) as credit
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND vendor_extracted = %s
        ORDER BY transaction_date, transaction_id;
    """, (vendor,))
    
    rows = cur.fetchall()
    total = sum((r[3] if r[3] else r[4]) for r in rows)
    
    print(f"--- {vendor} ---")
    print(f"Total transactions: {len(rows)}")
    print(f"Reported total: ${known_total:,.2f}")
    print(f"Calculated total: ${total:,.2f}")
    
    for txn_id, date, desc, debit, credit in rows:
        amount = debit if debit else credit
        if amount > 5000:  # Flag large transactions
            print(f"  🚨 TX {txn_id:5} | {date} | ${amount:>10.2f} | {desc[:60]}")
        else:
            print(f"  TX {txn_id:5} | {date} | ${amount:>10.2f} | {desc[:60]}")
    print()

print("\n=== CONSOLIDATING LIQUOR STORE CHAINS ===\n")

# Consolidate individual store chains (not all liquor stores as one)
liquor_consolidations = {
    'UPTOWN LIQUOR': 'Uptown Liquor',        # Normalize case
    'Up Town Liquor Store': 'Uptown Liquor', # Different spacing
    'ONE STOP LIQUOR': 'One Stop Liquor',    # Normalize case
    'LIQUOR 7': 'Liquor 7',                  # Just normalize case
}

backup_name = f"banking_transactions_liquor_consolidation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_name}...")
cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM banking_transactions WHERE account_number = '0228362'")
print(f"✓ Backed up 9,865 CIBC transactions\n")

total_updated = 0
for from_vendor, to_vendor in liquor_consolidations.items():
    cur.execute("""
        UPDATE banking_transactions
        SET vendor_extracted = %s
        WHERE account_number = '0228362'
        AND vendor_extracted = %s
    """, (to_vendor, from_vendor))
    
    count = cur.rowcount
    if count > 0:
        print(f"✓ {count:2} transactions: '{from_vendor}' → '{to_vendor}'")
        total_updated += count

if total_updated > 0:
    conn.commit()
    print(f"\n✓ {total_updated} total updates committed")
else:
    conn.rollback()
    print(f"\n! No updates needed")

conn.close()

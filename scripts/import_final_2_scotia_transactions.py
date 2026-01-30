#!/usr/bin/env python3
"""
Import the 2 missing Scotia 2014 transactions (both on 2014-06-23)
"""

import psycopg2
from datetime import datetime

SCOTIA_ACCOUNT = '903990106011'

# The 2 missing transactions from 2014-06-23
missing_transactions = [
    {
        'date': '2014-06-23',
        'description': 'VCARD DEPOSIT',
        'debit': 0.00,
        'credit': 580.01
    },
    {
        'date': '2014-06-23',
        'description': 'MCARD DEPOSIT',
        'debit': 0.00,
        'credit': 508.16
    }
]

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("IMPORTING 2 MISSING SCOTIA 2014 TRANSACTIONS")
print("="*80)

imported_count = 0

for trans in missing_transactions:
    # Check if already exists
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date = %s
          AND description = %s
          AND debit_amount = %s
          AND credit_amount = %s
    """, (SCOTIA_ACCOUNT, trans['date'], trans['description'], trans['debit'], trans['credit']))
    
    if cur.fetchone()[0] > 0:
        print(f"⚠️  Already exists: {trans['date']} {trans['description']} ${trans['credit']:.2f}")
        continue
    
    # Insert the transaction
    cur.execute("""
        INSERT INTO banking_transactions (
            account_number, transaction_date, description,
            debit_amount, credit_amount, balance,
            source_file, import_batch, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, NULL,
            '2013_scotia_transactions_for_editingfinal.xlsx',
            'manual_missing_2014_06_23', NOW()
        )
    """, (
        SCOTIA_ACCOUNT,
        trans['date'],
        trans['description'],
        trans['debit'] if trans['debit'] > 0 else None,
        trans['credit'] if trans['credit'] > 0 else None
    ))
    
    imported_count += 1
    print(f"✅ Imported: {trans['date']} {trans['description']:<30} Debit: ${trans['debit']:>8.2f}  Credit: ${trans['credit']:>8.2f}")

conn.commit()

print(f"\n{'='*80}")
print(f"✅ Successfully imported {imported_count} missing transactions")
print(f"{'='*80}")

# Verify final count
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE account_number = %s
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""", (SCOTIA_ACCOUNT,))

print("\nFINAL COUNTS:")
print(f"{'Year':<6} {'Count':<8} {'Total Debits':<18} {'Total Credits':<18}")
print("-" * 60)

total_count = 0
for row in cur.fetchall():
    year = int(row[0])
    count = row[1]
    debits = float(row[2] or 0)
    credits = float(row[3] or 0)
    total_count += count
    print(f"{year:<6} {count:<8} ${debits:>15,.2f}  ${credits:>15,.2f}")

print("-" * 60)
print(f"TOTAL: {total_count} transactions")
print(f"EXPECTED: 2,627 transactions (1,739 from 2013 + 888 from 2014)")

if total_count == 2627:
    print("✅ PERFECT MATCH! All transactions imported.")
else:
    print(f"⚠️  Still missing {2627 - total_count} transactions")

cur.close()
conn.close()

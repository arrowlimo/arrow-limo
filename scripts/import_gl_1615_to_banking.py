#!/usr/bin/env python3
"""
Import account 1615 transactions from general_ledger to banking_transactions
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("IMPORTING ACCOUNT 1615 FROM GENERAL_LEDGER TO BANKING_TRANSACTIONS")
print("="*80)

# First, check current state
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615'")
current_count = cur.fetchone()[0]
print(f"\nCurrent banking_transactions 1615 count: {current_count:,}")

cur.execute("SELECT COUNT(*) FROM general_ledger WHERE account LIKE '%1615%'")
gl_count = cur.fetchone()[0]
print(f"General_ledger 1615 count: {gl_count:,}")

# Get transactions from general_ledger
print("\nRetrieving transactions from general_ledger...")
cur.execute("""
    SELECT 
        id,
        date,
        transaction_type,
        num,
        name,
        memo_description,
        account,
        debit,
        credit,
        balance,
        source_file
    FROM general_ledger
    WHERE account LIKE '%1615%'
    ORDER BY date, id
""")

gl_transactions = cur.fetchall()
print(f"Retrieved {len(gl_transactions):,} transactions")

# Prepare for import
imported_count = 0
skipped_count = 0
error_count = 0

print("\nImporting transactions...")
print("-" * 80)

for row in gl_transactions:
    gl_id, date, trans_type, num, name, memo, account, debit, credit, balance, source_file = row
    
    # Skip if no date
    if not date:
        skipped_count += 1
        continue
    
    # Build description
    description_parts = []
    if trans_type:
        description_parts.append(trans_type)
    if name:
        description_parts.append(name)
    if memo and memo != 'nan':
        description_parts.append(memo)
    
    description = ' - '.join(description_parts) if description_parts else 'Transaction'
    
    # Determine amount (use debit as positive, credit as negative for bank perspective)
    debit_amount = float(debit) if debit else 0.0
    credit_amount = float(credit) if credit else 0.0
    
    # Check if already exists (by date + amounts + similar description)
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '1615'
          AND transaction_date = %s
          AND ABS(COALESCE(debit_amount, 0) - %s) < 0.01
          AND ABS(COALESCE(credit_amount, 0) - %s) < 0.01
    """, (date, debit_amount, credit_amount))
    
    exists = cur.fetchone()[0] > 0
    
    if exists:
        skipped_count += 1
        continue
    
    # Insert into banking_transactions
    try:
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance,
                source_file,
                created_at
            ) VALUES (
                '1615',
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            date,
            description[:500] if description else None,  # Limit length
            debit_amount if debit_amount > 0 else None,
            credit_amount if credit_amount > 0 else None,
            float(balance) if balance else None,
            f'general_ledger:1000 CIBC Bank 1615 (GL ID:{gl_id})',
            datetime.now()
        ))
        
        imported_count += 1
        
        if imported_count % 100 == 0:
            print(f"  Imported {imported_count:,} transactions...")
            
    except Exception as e:
        error_count += 1
        print(f"  ❌ Error importing GL ID {gl_id}: {e}")

# Commit changes
print("\n" + "="*80)
print("COMMITTING CHANGES...")
conn.commit()
print("✅ COMMITTED")

# Verify final count
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615'")
final_count = cur.fetchone()[0]

print("\n" + "="*80)
print("IMPORT SUMMARY")
print("="*80)
print(f"General_ledger transactions: {gl_count:,}")
print(f"Imported: {imported_count:,}")
print(f"Skipped (duplicates/no date): {skipped_count:,}")
print(f"Errors: {error_count:,}")
print(f"\nBanking_transactions before: {current_count:,}")
print(f"Banking_transactions after: {final_count:,}")
print(f"Net increase: {final_count - current_count:,}")

# Verify year breakdown
print("\n" + "="*80)
print("YEAR BREAKDOWN AFTER IMPORT")
print("="*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

print(f"\n{'Year':<6} {'Count':<8}")
print("-" * 20)
for row in cur.fetchall():
    year = int(row[0]) if row[0] else "NULL"
    count = row[1]
    print(f"{year:<6} {count:<8,}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ IMPORT COMPLETE - Account 1615 data restored!")
print("="*80)

"""Export Scotia Bank 2012 transactions to Excel with all corrections applied."""

import psycopg2
import pandas as pd
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)

print("="*80)
print("SCOTIA BANK 2012 EXPORT TO EXCEL")
print("="*80)
print()

# Get all 2012 transactions
cur = conn.cursor()
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        vendor_extracted,
        category,
        created_at,
        updated_at
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, transaction_id
""")

rows = cur.fetchall()
print(f"Found {len(rows):,} transactions for 2012")
print()

# Create DataFrame
df = pd.DataFrame(rows, columns=[
    'transaction_id', 'date', 'description', 'debit', 'credit', 
    'balance', 'vendor', 'category', 'created_at', 'updated_at'
])

# Format amounts
df['debit'] = df['debit'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
df['credit'] = df['credit'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
df['balance'] = df['balance'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")

# Monthly summary
print("="*80)
print("MONTHLY SUMMARY")
print("="*80)
print()
print(f"{'Month':<12} {'Count':>8} {'Debits':>15} {'Credits':>15} {'Net':>15}")
print("-"*70)

cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as txn_count,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits,
        SUM(COALESCE(credit_amount, 0)) - SUM(COALESCE(debit_amount, 0)) as net
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
    ORDER BY month
""")

year_total = 0
year_debits = 0
year_credits = 0
for month, count, debits, credits, net in cur.fetchall():
    year_total += count
    year_debits += float(debits) if debits else 0
    year_credits += float(credits) if credits else 0
    net_val = float(net) if net else 0
    print(f"{month:<12} {count:>8,} ${debits:>13,.2f} ${credits:>13,.2f} ${net_val:>13,.2f}")

print("-"*70)
year_net = year_credits - year_debits
print(f"{'2012 Total':<12} {year_total:>8,} ${year_debits:>13,.2f} ${year_credits:>13,.2f} ${year_net:>13,.2f}")
print()

# Balance verification
cur.execute("""
    SELECT transaction_date, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
    LIMIT 1
""")
first = cur.fetchone()

cur.execute("""
    SELECT transaction_date, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date DESC
    LIMIT 1
""")
last = cur.fetchone()

print("="*80)
print("BALANCE VERIFICATION")
print("="*80)
print()
print(f"Opening Balance ({first[0]}): ${first[1]:,.2f}")
print(f"Closing Balance ({last[0]}): ${last[1]:,.2f}")
print()

# Check for issues
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND balance IS NULL
""")
null_count = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND description LIKE '%[DUPLICATE?]%'
""")
dup_count = cur.fetchone()[0]

print("="*80)
print("DATA QUALITY CHECKS")
print("="*80)
print()
print(f"NULL Balances: {null_count:,} {'✓ GOOD' if null_count == 0 else '⚠ NEEDS FIX'}")
print(f"Marked Duplicates: {dup_count:,} {'⚠ REVIEW' if dup_count > 0 else '✓ NONE'}")
print()

# Export to Excel
output_path = r"L:\limo\data\scotia_2012_transactions_updated.xlsx"
print(f"Exporting to: {output_path}")
print()

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    # Main transactions sheet
    df.to_excel(writer, sheet_name='Transactions', index=False)
    
    # Monthly summary sheet
    cur.execute("""
        SELECT 
            TO_CHAR(transaction_date, 'YYYY-MM') as month,
            COUNT(*) as transactions,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            SUM(COALESCE(credit_amount, 0)) as total_credits,
            SUM(COALESCE(credit_amount, 0)) - SUM(COALESCE(debit_amount, 0)) as net_change,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
        ORDER BY month
    """)
    
    summary_rows = cur.fetchall()
    summary_df = pd.DataFrame(summary_rows, columns=[
        'Month', 'Transactions', 'Total Debits', 'Total Credits', 
        'Net Change', 'Min Balance', 'Max Balance'
    ])
    summary_df.to_excel(writer, sheet_name='Monthly Summary', index=False)
    
    # If there are duplicates, create a sheet for them
    if dup_count > 0:
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND description LIKE '%[DUPLICATE?]%'
            ORDER BY transaction_date
        """)
        
        dup_rows = cur.fetchall()
        dup_df = pd.DataFrame(dup_rows, columns=[
            'transaction_id', 'date', 'description', 'debit', 'credit', 'balance'
        ])
        dup_df.to_excel(writer, sheet_name='Marked Duplicates', index=False)

print("✓ Export complete!")
print()
print("="*80)
print("SUMMARY")
print("="*80)
print()
print(f"Total 2012 Transactions: {len(rows):,}")
print(f"NULL Balances: {null_count:,}")
print(f"Marked Duplicates: {dup_count:,}")
print(f"Excel File: {output_path}")
print()
print("Status: {'✓ READY TO USE' if null_count == 0 else '⚠ FIX NULLS FIRST'}")
print()

cur.close()
conn.close()

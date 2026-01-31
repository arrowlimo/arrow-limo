"""
Check for duplicate transactions in CIBC 8362 2014-2017 data
Same date + same amount = potential duplicates
User added numbers to descriptions to differentiate
"""
import psycopg2
import pandas as pd

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

print("=" * 100)
print("DUPLICATE TRANSACTION CHECK - CIBC 8362 (2014-2017)")
print("=" * 100)

query = """
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE bank_id = 1
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    ORDER BY transaction_date, debit_amount, credit_amount, description
"""

df = pd.read_sql(query, conn)

print(f"\nTotal transactions: {len(df):,}\n")

# Find potential duplicates (same date + same debit amount)
print("=" * 100)
print("DEBIT DUPLICATES (same date + same debit amount)")
print("=" * 100)

debit_df = df[df['debit_amount'].notna()].copy()
debit_df['dup_key'] = debit_df['transaction_date'].astype(str) + '_' + debit_df['debit_amount'].astype(str)
debit_dups = debit_df[debit_df.duplicated(subset=['dup_key'], keep=False)].sort_values(['transaction_date', 'debit_amount'])

if len(debit_dups) > 0:
    print(f"\n⚠️ Found {len(debit_dups)} debit transactions with same date + amount:\n")
    
    current_key = None
    for idx, row in debit_dups.iterrows():
        date_str = str(row['transaction_date'])
        key = f"{date_str}_{row['debit_amount']:.2f}"
        if key != current_key:
            if current_key:
                print()
            print(f"📅 {date_str} - ${row['debit_amount']:.2f}:")
            current_key = key
        
        # Check if description has numbering
        has_number = any(char.isdigit() for char in row['description'][-5:])
        marker = "✓" if has_number else "⚠️"
        print(f"   {marker} ID {row['transaction_id']}: {row['description'][:70]}")
else:
    print("✅ No debit duplicates found")

# Find potential duplicates (same date + same credit amount)
print("\n" + "=" * 100)
print("CREDIT DUPLICATES (same date + same credit amount)")
print("=" * 100)

credit_df = df[df['credit_amount'].notna()].copy()
credit_df['dup_key'] = credit_df['transaction_date'].astype(str) + '_' + credit_df['credit_amount'].astype(str)
credit_dups = credit_df[credit_df.duplicated(subset=['dup_key'], keep=False)].sort_values(['transaction_date', 'credit_amount'])

if len(credit_dups) > 0:
    print(f"\n⚠️ Found {len(credit_dups)} credit transactions with same date + amount:\n")
    
    current_key = None
    for idx, row in credit_dups.iterrows():
        date_str = str(row['transaction_date'])
        key = f"{date_str}_{row['credit_amount']:.2f}"
        if key != current_key:
            if current_key:
                print()
            print(f"📅 {date_str} - ${row['credit_amount']:.2f}:")
            current_key = key
        
        # Check if description has numbering
        has_number = any(char.isdigit() for char in row['description'][-5:])
        marker = "✓" if has_number else "⚠️"
        print(f"   {marker} ID {row['transaction_id']}: {row['description'][:70]}")
else:
    print("✅ No credit duplicates found")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total transactions: {len(df):,}")
print(f"Debit duplicates (same date+amount): {len(debit_dups)}")
print(f"Credit duplicates (same date+amount): {len(credit_dups)}")
print(f"\n✓ = Description has numbering (user added)")
print(f"⚠️ = No numbering (may need review)")

conn.close()

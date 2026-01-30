"""
Comprehensive SQUARE transaction analysis for verification
Lists all SQUARE-related transactions to verify correct categorization
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
print("SQUARE TRANSACTION VERIFICATION REPORT")
print("All SQUARE-related transactions from CIBC 8362 (2014-2017)")
print("=" * 100)

# Get all SQUARE transactions
query = """
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        transaction_id
    FROM banking_transactions
    WHERE bank_id = 1
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%SQUARE%'
    ORDER BY transaction_date, transaction_id
"""

df = pd.read_sql(query, conn)

if len(df) == 0:
    print("\n❌ No SQUARE transactions found (data may have been deleted)")
    conn.close()
    exit(0)

print(f"\n📊 Total SQUARE transactions: {len(df)}\n")

# Categorize SQUARE transactions
square_deposit_debit = df[(df['description'].str.upper().str.contains('SQUARE DEPOSIT')) & (df['debit_amount'].notna())]
square_deposit_credit = df[(df['description'].str.upper().str.contains('SQUARE DEPOSIT')) & (df['credit_amount'].notna())]
square_withdrawal_debit = df[(df['description'].str.upper().str.contains('SQUARE WITHDRAWAL')) & (df['debit_amount'].notna())]
square_withdrawal_credit = df[(df['description'].str.upper().str.contains('SQUARE WITHDRAWAL')) & (df['credit_amount'].notna())]
square_other = df[~df['description'].str.upper().str.contains('DEPOSIT|WITHDRAWAL')]

print("=" * 100)
print("SQUARE DEPOSIT in DEBIT column (ERRORS - should be fees or vendor payments)")
print("=" * 100)
if len(square_deposit_debit) > 0:
    print(f"\n⚠️ Found {len(square_deposit_debit)} SQUARE DEPOSIT as debits:\n")
    print(f"{'Date':<12} {'Amount':<12} {'Description':<50}")
    print("-" * 100)
    for _, row in square_deposit_debit.iterrows():
        print(f"{str(row['transaction_date']):<12} ${row['debit_amount']:>9.2f}   {row['description']}")
    print(f"\nTotal: ${square_deposit_debit['debit_amount'].sum():,.2f}")
    print("\n📝 ACTION: Change these to 'SQUARE FEE' or correct vendor name (except WOK BOX $10.49)")
else:
    print("✅ None found")

print("\n" + "=" * 100)
print("SQUARE DEPOSIT in CREDIT column (CORRECT - Square payouts)")
print("=" * 100)
if len(square_deposit_credit) > 0:
    print(f"\n✅ Found {len(square_deposit_credit)} SQUARE DEPOSIT as credits:\n")
    print(f"{'Date':<12} {'Amount':<12} {'Description':<50}")
    print("-" * 100)
    for _, row in square_deposit_credit.iterrows():
        print(f"{str(row['transaction_date']):<12} ${row['credit_amount']:>9.2f}   {row['description']}")
    print(f"\nTotal: ${square_deposit_credit['credit_amount'].sum():,.2f}")
else:
    print("None found")

print("\n" + "=" * 100)
print("SQUARE WITHDRAWAL in DEBIT column (CORRECT - Refunds/Disputes)")
print("=" * 100)
if len(square_withdrawal_debit) > 0:
    print(f"\n✅ Found {len(square_withdrawal_debit)} SQUARE WITHDRAWAL as debits:\n")
    print(f"{'Date':<12} {'Amount':<12} {'Description':<50}")
    print("-" * 100)
    for _, row in square_withdrawal_debit.iterrows():
        print(f"{str(row['transaction_date']):<12} ${row['debit_amount']:>9.2f}   {row['description']}")
    print(f"\nTotal: ${square_withdrawal_debit['debit_amount'].sum():,.2f}")
else:
    print("None found")

print("\n" + "=" * 100)
print("SQUARE WITHDRAWAL in CREDIT column (ERROR - Should be in debit)")
print("=" * 100)
if len(square_withdrawal_credit) > 0:
    print(f"\n⚠️ Found {len(square_withdrawal_credit)} SQUARE WITHDRAWAL as credits:\n")
    print(f"{'Date':<12} {'Amount':<12} {'Description':<50}")
    print("-" * 100)
    for _, row in square_withdrawal_credit.iterrows():
        print(f"{str(row['transaction_date']):<12} ${row['credit_amount']:>9.2f}   {row['description']}")
    print(f"\nTotal: ${square_withdrawal_credit['credit_amount'].sum():,.2f}")
    print("\n📝 ACTION: These need Excel correction - move to debit column")
else:
    print("✅ None found")

print("\n" + "=" * 100)
print("OTHER SQUARE transactions")
print("=" * 100)
if len(square_other) > 0:
    print(f"\nFound {len(square_other)} other SQUARE transactions:\n")
    for _, row in square_other.iterrows():
        debit_str = f"${row['debit_amount']:.2f}" if pd.notna(row['debit_amount']) else "None"
        credit_str = f"${row['credit_amount']:.2f}" if pd.notna(row['credit_amount']) else "None"
        print(f"{row['transaction_date']} - {row['description'][:50]} - Debit: {debit_str}, Credit: {credit_str}")
else:
    print("None found")

# Summary
print("\n" + "=" * 100)
print("VERIFICATION SUMMARY")
print("=" * 100)
print(f"Total SQUARE transactions: {len(df)}")
print(f"⚠️ SQUARE DEPOSIT in debit (need fixing): {len(square_deposit_debit)}")
print(f"✅ SQUARE DEPOSIT in credit (correct): {len(square_deposit_credit)}")
print(f"✅ SQUARE WITHDRAWAL in debit (correct): {len(square_withdrawal_debit)}")
print(f"⚠️ SQUARE WITHDRAWAL in credit (need fixing): {len(square_withdrawal_credit)}")
print(f"Other SQUARE: {len(square_other)}")

total_errors = len(square_deposit_debit) + len(square_withdrawal_credit)
if total_errors > 0:
    print(f"\n❌ TOTAL ERRORS TO FIX IN EXCEL: {total_errors}")
else:
    print("\n✅ All SQUARE transactions correctly categorized")

# Export to CSV for verification
output_file = r"L:\limo\reports\square_transactions_verification_2014_2017.csv"
df.to_csv(output_file, index=False)
print(f"\n📄 Full report exported to: {output_file}")

conn.close()

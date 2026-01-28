"""
Verify that descriptions containing DEPOSIT/WITHDRAWAL match actual transaction direction
Checks CIBC 8362 2014-2017 imported data for mismatches
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

print("=" * 100)
print("DEPOSIT/WITHDRAWAL DESCRIPTION VERIFICATION - CIBC 8362 (2014-2017)")
print("=" * 100)

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Check 1: Descriptions with "DEPOSIT" that are actually WITHDRAWALS (debits)
print("\n🔍 CHECK 1: Descriptions with 'DEPOSIT' that are actually WITHDRAWALS (debit_amount > 0)")
print("-" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%DEPOSIT%'
    AND debit_amount IS NOT NULL
    AND debit_amount > 0
    ORDER BY transaction_date, transaction_id
""")

mismatches_deposit = cur.fetchall()

if mismatches_deposit:
    print(f"⚠️ Found {len(mismatches_deposit)} MISMATCHES - 'DEPOSIT' in description but money going OUT:")
    print(f"\n{'Date':<12} {'ID':<8} {'Description':<50} {'Debit':<12} {'Credit':<12} {'Balance':<12}")
    print("-" * 100)
    for tid, date, desc, debit, credit, balance in mismatches_deposit[:50]:  # Show first 50
        print(f"{str(date):<12} {tid:<8} {desc[:50]:<50} ${debit:>10.2f} {str(credit) if credit else 'None':<12} ${balance:>10.2f}")
    if len(mismatches_deposit) > 50:
        print(f"\n... and {len(mismatches_deposit) - 50} more")
else:
    print("✅ No mismatches found - all 'DEPOSIT' descriptions have credit_amount")

# Check 2: Descriptions with "WITHDRAWAL" that are actually DEPOSITS (credits)
print("\n" + "=" * 100)
print("🔍 CHECK 2: Descriptions with 'WITHDRAWAL' that are actually DEPOSITS (credit_amount > 0)")
print("-" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%WITHDRAWAL%'
    AND credit_amount IS NOT NULL
    AND credit_amount > 0
    ORDER BY transaction_date, transaction_id
""")

mismatches_withdrawal = cur.fetchall()

if mismatches_withdrawal:
    print(f"⚠️ Found {len(mismatches_withdrawal)} MISMATCHES - 'WITHDRAWAL' in description but money coming IN:")
    print(f"\n{'Date':<12} {'ID':<8} {'Description':<50} {'Debit':<12} {'Credit':<12} {'Balance':<12}")
    print("-" * 100)
    for tid, date, desc, debit, credit, balance in mismatches_withdrawal[:50]:
        print(f"{str(date):<12} {tid:<8} {desc[:50]:<50} {str(debit) if debit else 'None':<12} ${credit:>10.2f} ${balance:>10.2f}")
    if len(mismatches_withdrawal) > 50:
        print(f"\n... and {len(mismatches_withdrawal) - 50} more")
else:
    print("✅ No mismatches found - all 'WITHDRAWAL' descriptions have debit_amount")

# Check 3: Generic "BANK TRANSFER" or "TRANSFER" - show breakdown
print("\n" + "=" * 100)
print("🔍 CHECK 3: Generic 'BANK TRANSFER' or 'TRANSFER' descriptions - breakdown by type")
print("-" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN debit_amount > 0 THEN 'WITHDRAWAL'
            WHEN credit_amount > 0 THEN 'DEPOSIT'
            ELSE 'ZERO'
        END as actual_type,
        COUNT(*) as count,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND (UPPER(description) LIKE '%BANK TRANSFER%' OR UPPER(description) = 'TRANSFER')
    GROUP BY actual_type
    ORDER BY actual_type
""")

transfer_breakdown = cur.fetchall()

if transfer_breakdown:
    print(f"{'Actual Type':<15} {'Count':<10} {'Total Debits':<15} {'Total Credits':<15}")
    print("-" * 100)
    for actual_type, count, total_debits, total_credits in transfer_breakdown:
        print(f"{actual_type:<15} {count:<10} ${total_debits:>12.2f} ${total_credits:>12.2f}")
else:
    print("No bank transfer transactions found")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"❌ 'DEPOSIT' descriptions with debit_amount: {len(mismatches_deposit)}")
print(f"❌ 'WITHDRAWAL' descriptions with credit_amount: {len(mismatches_withdrawal)}")
total_issues = len(mismatches_deposit) + len(mismatches_withdrawal)

if total_issues > 0:
    print(f"\n⚠️ TOTAL MISMATCHES: {total_issues}")
    print("\n📝 ACTION NEEDED: Review Excel file and correct description labels")
    print("   - Change 'DEPOSIT' to 'WITHDRAWAL' for debit transactions")
    print("   - Change 'WITHDRAWAL' to 'DEPOSIT' for credit transactions")
    print("   - Re-run import after corrections")
else:
    print("\n✅ All deposit/withdrawal descriptions match transaction directions!")

cur.close()
conn.close()

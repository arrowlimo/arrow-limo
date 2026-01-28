"""
Analyze bank transfer transactions to identify source/destination accounts
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("BANK TRANSFER ANALYSIS - CIBC 8362 (2014-2017)")
print("=" * 120)

# Get all bank transfer transactions
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount,
        r.receipt_id,
        r.vendor_name,
        r.gross_amount
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.bank_id = 1
    AND bt.source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(bt.description) LIKE '%BANK TRANSFER%'
    ORDER BY bt.transaction_date
""")

transfers = cur.fetchall()

print(f"\n📊 Found {len(transfers)} bank transfer transactions\n")

if len(transfers) == 0:
    print("No bank transfers found")
    cur.close()
    conn.close()
    exit(0)

# Analyze patterns
print("=" * 120)
print("SAMPLE BANK TRANSFERS")
print("=" * 120)
print(f"{'Date':<12} {'Description':<50} {'Debit':<15} {'Credit':<15} {'Receipt ID':<12}")
print("=" * 120)

debits = []
credits = []

for i, (txn_id, date, desc, debit, credit, receipt_id, vendor, amount) in enumerate(transfers[:30]):
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    print(f"{str(date):<12} {desc[:50]:<50} {debit_str:>14} {credit_str:>14} {receipt_id or 'None':<12}")
    
    if debit:
        debits.append((txn_id, date, desc, debit))
    else:
        credits.append((txn_id, date, desc, credit))

if len(transfers) > 30:
    print(f"\n... and {len(transfers) - 30} more")

# Summary
print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print(f"Total transfers: {len(transfers)}")
print(f"Debits (money out): {len(debits)}")
print(f"Credits (money in): {len(credits)}")

# Check for matching pairs (same amount, opposite direction)
print("\n" + "=" * 120)
print("POTENTIAL MATCHING PAIRS (same amount within 3 days)")
print("=" * 120)

matched_pairs = []
for debit_id, debit_date, debit_desc, debit_amt in debits:
    for credit_id, credit_date, credit_desc, credit_amt in credits:
        # Check if amounts match and dates are close
        date_diff = abs((credit_date - debit_date).days)
        if abs(debit_amt - credit_amt) < 0.01 and date_diff <= 3:
            matched_pairs.append({
                'debit_id': debit_id,
                'debit_date': debit_date,
                'debit_desc': debit_desc,
                'debit_amt': debit_amt,
                'credit_id': credit_id,
                'credit_date': credit_date,
                'credit_desc': credit_desc,
                'credit_amt': credit_amt,
                'date_diff': date_diff
            })

if matched_pairs:
    print(f"\n{'Amount':<15} {'Date Diff':<12} {'Debit Date':<12} {'Credit Date':<12}")
    print("-" * 120)
    for pair in matched_pairs[:20]:
        print(f"${pair['debit_amt']:>13,.2f} {pair['date_diff']:>11} days {str(pair['debit_date']):<12} {str(pair['credit_date']):<12}")
    
    if len(matched_pairs) > 20:
        print(f"\n... and {len(matched_pairs) - 20} more pairs")
    
    print(f"\nTotal potential matched pairs: {len(matched_pairs)}")
else:
    print("No obvious matching pairs found")

# Check if transfers are to/from Scotia Bank (bank_id = 2)
print("\n" + "=" * 120)
print("CHECKING FOR SCOTIA BANK TRANSFERS")
print("=" * 120)

cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE bank_id = 2
    AND source_file LIKE '%Scotia%'
""")

scotia_count = cur.fetchone()[0]
print(f"Scotia Bank transactions in database: {scotia_count:,}")

if scotia_count > 0:
    print("\n✅ Scotia Bank account exists - transfers may be inter-account")
    print("   Source account: CIBC 0228362 (bank_id = 1)")
    print("   Destination account: Scotia 903990106011 (bank_id = 2)")
else:
    print("\n⚠️  Scotia Bank account not found - transfers may be to external accounts")

cur.close()
conn.close()

print("\n✅ Analysis complete")

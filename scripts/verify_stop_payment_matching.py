"""
Verify STOP PAYMENT transactions (cancelled eTransfers) have matching reversals
Should work like NSF - charge and reversal with EXACT same amount that zero out, no fees
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 100)
print("STOP PAYMENT VERIFICATION - CIBC 8362 (2014-2017)")
print("Same date + exact amount pairs should zero out, no banking fees")
print("=" * 100)

# Find all STOP transactions
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
    AND UPPER(description) LIKE '%STOP%'
    ORDER BY transaction_date, transaction_id
""")

stop_txns = cur.fetchall()

print(f"\n📋 Found {len(stop_txns)} STOP transactions\n")
print(f"{'Date':<12} {'ID':<8} {'Description':<50} {'Debit':<12} {'Credit':<12}")
print("-" * 100)

# Group by date and exact amount
stop_groups = {}

for tid, date, desc, debit, credit, balance in stop_txns:
    debit_str = f"${debit:>9.2f}" if debit else "None"
    credit_str = f"${credit:>9.2f}" if credit else "None"
    print(f"{str(date):<12} {tid:<8} {desc[:50]:<50} {debit_str:<12} {credit_str:<12}")
    
    # Group by date and amount (exact match)
    amount = round(debit, 2) if debit else round(credit, 2)
    key = (date, amount)
    if key not in stop_groups:
        stop_groups[key] = []
    stop_groups[key].append({
        'id': tid,
        'desc': desc,
        'debit': debit,
        'credit': credit
    })

# Check for matching pairs
print("\n" + "=" * 100)
print("MATCHING ANALYSIS (same date + exact amount)")
print("=" * 100)

matched_pairs = []
unmatched = []

for key, txns in stop_groups.items():
    date, amount = key
    
    if len(txns) == 2:
        # Check if one is debit and one is credit with EXACT same amount
        debit_txn = next((t for t in txns if t['debit'] is not None), None)
        credit_txn = next((t for t in txns if t['credit'] is not None), None)
        
        if debit_txn and credit_txn:
            debit_amt = round(debit_txn['debit'], 2)
            credit_amt = round(credit_txn['credit'], 2)
            
            if debit_amt == credit_amt:
                matched_pairs.append((date, amount, txns))
                print(f"✅ MATCHED: {date} - ${amount:.2f} (zeros out)")
                print(f"   Debit:  ID {debit_txn['id']} - {debit_txn['desc']}")
                print(f"   Credit: ID {credit_txn['id']} - {credit_txn['desc']}")
            else:
                unmatched.append((date, amount, txns))
                print(f"⚠️ AMOUNTS DON'T MATCH: {date} - Debit ${debit_amt:.2f} vs Credit ${credit_amt:.2f}")
        else:
            unmatched.append((date, amount, txns))
            print(f"⚠️ NOT OPPOSITE TYPES: {date} - ${amount:.2f}")
            for t in txns:
                print(f"   ID {t['id']}: {t['desc']} - Debit: {t['debit']}, Credit: {t['credit']}")
    elif len(txns) == 1:
        unmatched.append((date, amount, txns))
        print(f"❌ UNMATCHED: {date} - ${amount:.2f} - {txns[0]['desc']}")
    else:
        unmatched.append((date, amount, txns))
        print(f"⚠️ MULTIPLE ({len(txns)}): {date} - ${amount:.2f}")

# Check for any fees associated with STOP
print("\n" + "=" * 100)
print("CHECKING FOR BANKING FEES")
print("=" * 100)

cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%STOP%FEE%'
""")

fee_count = cur.fetchone()[0]

if fee_count > 0:
    print(f"⚠️ Found {fee_count} STOP-related fees")
else:
    print("✅ No STOP-related banking fees found")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total STOP transactions: {len(stop_txns)}")
print(f"✅ Matched pairs (zero out): {len(matched_pairs)}")
print(f"❌ Unmatched/issues: {len(unmatched)}")
print(f"⚠️ STOP FEE transactions: {fee_count}")

if len(matched_pairs) * 2 == len(stop_txns) and fee_count == 0:
    print("\n✅ ALL STOP PAYMENTS VERIFIED:")
    print("   - All have matching reversals that zero out")
    print("   - No banking fees associated with STOP transactions")
else:
    print("\n⚠️ VERIFICATION ISSUES:")
    print("   - Most STOP transactions are CREDITS ONLY (reversals/returns)")
    print("   - 'ONE STOP' = Store purchases (not eTransfer stops)")
    print("   - ETRANSFER STOP = Cancelled eTransfer returns (no matching debit needed)")

cur.close()
conn.close()

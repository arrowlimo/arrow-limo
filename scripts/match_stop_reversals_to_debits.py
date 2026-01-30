"""
Match STOP PAYMENT reversals to original debit transactions (like NSF pairs)
STOP transactions are CREDITS that reverse original DEBITS
Account for typo: STOPP (double P)
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
print("STOP PAYMENT REVERSAL MATCHING - Find original debits that match STOP credits")
print("=" * 100)

# Get all STOP transactions (including STOPP typo)
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
    AND (UPPER(description) LIKE '%STOP%' OR UPPER(description) LIKE '%STOPP%')
    AND credit_amount IS NOT NULL
    AND credit_amount > 0
    ORDER BY transaction_date, transaction_id
""")

stop_credits = cur.fetchall()

print(f"\n📋 Found {len(stop_credits)} STOP reversals (credits)\n")
print(f"{'Date':<12} {'ID':<8} {'Amount':<12} {'Description':<50}")
print("-" * 100)

matched_count = 0
unmatched_stops = []

for tid, date, desc, debit, credit, balance in stop_credits:
    print(f"{str(date):<12} {tid:<8} ${credit:>9.2f}   {desc[:50]:<50}")
    
    # Find matching original debit transaction with same amount
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE bank_id = 1
        AND debit_amount IS NOT NULL
        AND debit_amount = %s
        AND UPPER(description) NOT LIKE '%%STOP%%'
        AND transaction_date <= %s
        ORDER BY transaction_date DESC
        LIMIT 1
    """, (credit, date))
    
    matching_debit = cur.fetchone()
    
    if matching_debit:
        match_tid, match_date, match_desc, match_debit, match_credit = matching_debit
        days_diff = abs((date - match_date).days)
        print(f"  ✅ MATCHED debit: {match_date} ID {match_tid} ${match_debit:.2f} '{match_desc[:40]}' ({days_diff} days apart)")
        matched_count += 1
    else:
        print(f"  ❌ NO MATCHING DEBIT FOUND")
        unmatched_stops.append((date, desc, credit))

# Summary
print("\n" + "=" * 100)
print("MATCHING SUMMARY")
print("=" * 100)
print(f"Total STOP reversals: {len(stop_credits)}")
print(f"✅ Matched to original debit: {matched_count}")
print(f"❌ Unmatched (original debit not in 2014-2017): {len(unmatched_stops)}")

if unmatched_stops:
    print("\n⚠️ Unmatched STOP reversals (original debit likely in earlier period):")
    for date, desc, amount in unmatched_stops[:15]:
        print(f"   {date} ${amount:.2f} - {desc[:50]}")
    if len(unmatched_stops) > 15:
        print(f"   ... and {len(unmatched_stops) - 15} more")

# Check for STOPP typo
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE bank_id = 1
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%STOPP%'
""")

stopp_count = cur.fetchone()[0]

print(f"\n🔍 STOPP typo check: {stopp_count} transactions with 'STOPP' (double P)")
if stopp_count > 0:
    print("   Need to fix typo in Excel: STOPP → STOP")

cur.close()
conn.close()

print("\n✅ Analysis complete")

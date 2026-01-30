#!/usr/bin/env python3
"""
Verify NSF transactions by matching credit/debit pairs.
For each NSF debit, find if there was a prior credit of the same amount.
"""

import psycopg2
from datetime import timedelta

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 120)
print("NSF TRANSACTION VERIFICATION - MATCHING DEBITS TO PRIOR CREDITS")
print("=" * 120)

# Get all NSF debits (returned checks)
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND (description ILIKE '%RETURN%NSF%' OR description ILIKE '%NSF%' OR description ILIKE '%RETURNED%')
        AND debit_amount > 0
    ORDER BY transaction_date, debit_amount DESC
""")

nsf_debits = cur.fetchall()

print(f"\nFound {len(nsf_debits)} NSF/returned transactions (debits):")
print()
print(f"{'Trans ID':<10} {'Date':<12} {'Amount':<12} {'Description':<60}")
print("-" * 120)

for trans_id, date, desc, amount in nsf_debits:
    print(f"{trans_id:<10} {str(date):<12} ${amount:>9.2f} {desc[:60]}")

print("\n" + "=" * 120)
print("SEARCHING FOR MATCHING CREDITS (Prior deposits that bounced)")
print("=" * 120)

matched_pairs = []
unmatched_debits = []

for nsf_trans_id, nsf_date, nsf_desc, nsf_amount in nsf_debits:
    # Look for credits of same amount in previous 30 days
    date_start = nsf_date - timedelta(days=30)
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
            AND transaction_date BETWEEN %s AND %s
            AND ABS(credit_amount - %s) < 0.01
            AND credit_amount > 0
        ORDER BY ABS(transaction_date - %s::date), transaction_date DESC
        LIMIT 3
    """, (date_start, nsf_date, nsf_amount, nsf_date))
    
    prior_credits = cur.fetchall()
    
    if prior_credits:
        credit_id, credit_date, credit_desc, credit_amt = prior_credits[0]
        days_diff = (nsf_date - credit_date).days
        
        matched_pairs.append({
            'credit_id': credit_id,
            'credit_date': credit_date,
            'credit_desc': credit_desc,
            'credit_amt': credit_amt,
            'debit_id': nsf_trans_id,
            'debit_date': nsf_date,
            'debit_desc': nsf_desc,
            'debit_amt': nsf_amount,
            'days_diff': days_diff
        })
        
        print(f"\n✓ MATCHED PAIR (±{days_diff} days):")
        print(f"  Credit:  {credit_id:<10} {str(credit_date):<12} +${credit_amt:>9.2f} {credit_desc[:50]}")
        print(f"  NSF:     {nsf_trans_id:<10} {str(nsf_date):<12} -${nsf_amount:>9.2f} {nsf_desc[:50]}")
    else:
        unmatched_debits.append({
            'debit_id': nsf_trans_id,
            'debit_date': nsf_date,
            'debit_desc': nsf_desc,
            'debit_amt': nsf_amount
        })
        
        print(f"\n✗ NO MATCH FOUND:")
        print(f"  NSF:     {nsf_trans_id:<10} {str(nsf_date):<12} -${nsf_amount:>9.2f} {nsf_desc[:50]}")

print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)

print(f"\nTotal NSF transactions:      {len(nsf_debits)}")
print(f"Matched to prior credits:    {len(matched_pairs)}")
print(f"No matching credit found:    {len(unmatched_debits)}")

if matched_pairs:
    matched_total = sum(p['debit_amt'] for p in matched_pairs)
    print(f"\nMatched amount: ${matched_total:,.2f}")
    print("\n→ These are CUSTOMER CHECKS that bounced (deposited then reversed)")
    print("  - Customer gave us check")
    print("  - We deposited it (credit)")
    print("  - Customer's bank bounced it (debit reversal)")
    print("  - We need to collect from customer again")

if unmatched_debits:
    unmatched_total = sum(d['debit_amt'] for d in unmatched_debits)
    print(f"\nUnmatched amount: ${unmatched_total:,.2f}")
    print("\n→ These may be COMPANY CHECKS that bounced (we wrote check, it bounced)")
    print("  - We wrote check to vendor/payroll")
    print("  - Check bounced due to insufficient funds")
    print("  - Bank charged us NSF fee AND debited the check amount")

# Check for NSF service charges
print("\n" + "=" * 120)
print("NSF SERVICE CHARGES (Bank fees for bounced checks)")
print("=" * 120)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND description ILIKE '%NSF%CHARGE%'
        AND debit_amount > 0
    ORDER BY transaction_date
""")

nsf_charges = cur.fetchall()
if nsf_charges:
    print(f"\nFound {len(nsf_charges)} NSF service charges:")
    total_charges = 0
    for trans_id, date, desc, amount in nsf_charges:
        total_charges += amount
        print(f"  {trans_id:<10} {str(date):<12} ${amount:>9.2f} {desc[:60]}")
    print(f"\nTotal NSF charges: ${total_charges:,.2f}")

cur.close()
conn.close()

print("\n" + "=" * 120)

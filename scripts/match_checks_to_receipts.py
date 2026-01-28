#!/usr/bin/env python3
"""
Match unmatched checks to receipts by amount and date proximity.
This helps identify check payees when check register is unavailable.
"""

import psycopg2
from datetime import timedelta

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("MATCHING CHECKS TO RECEIPTS BY AMOUNT AND DATE")
print("=" * 120)

# Get unmatched checks from Scotia 2012
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND description ILIKE '%CHQ%'
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT mapped_bank_account_id 
            FROM receipts 
            WHERE mapped_bank_account_id IS NOT NULL
        )
    ORDER BY debit_amount DESC
""")

checks = cur.fetchall()
print(f"\nFound {len(checks)} unmatched checks")
print(f"Total amount: ${sum(c[3] for c in checks):,.2f}")

# Try to match each check to receipts
matches = []
no_match = []

print("\n" + "=" * 120)
print("SEARCHING FOR RECEIPT MATCHES")
print("=" * 120)
print(f"{'Check ID':<10} {'Date':<12} {'Amount':<12} {'Match Type':<15} {'Receipt':<60}")
print("-" * 120)

for trans_id, date, desc, amount in checks:
    # Try exact amount match first (within ±2 days)
    date_start = date - timedelta(days=2)
    date_end = date + timedelta(days=2)
    
    cur.execute("""
        SELECT id, receipt_date, vendor_name, description, gross_amount
        FROM receipts
        WHERE ABS(gross_amount - %s) < 0.01
            AND receipt_date BETWEEN %s AND %s
            AND (mapped_bank_account_id IS NULL OR mapped_bank_account_id != %s)
        ORDER BY ABS(receipt_date - %s)
        LIMIT 3
    """, (amount, date_start, date_end, trans_id, date))
    
    receipt_matches = cur.fetchall()
    
    if receipt_matches:
        for receipt_id, receipt_date, vendor, rdesc, ramount in receipt_matches:
            date_diff = abs((receipt_date - date).days)
            match_type = f"Exact (±{date_diff}d)"
            matches.append({
                'check_id': trans_id,
                'check_date': date,
                'check_amount': amount,
                'receipt_id': receipt_id,
                'receipt_date': receipt_date,
                'vendor': vendor,
                'amount_diff': abs(amount - ramount),
                'date_diff': date_diff
            })
            print(f"{trans_id:<10} {str(date):<12} ${amount:>9.2f} {match_type:<15} {receipt_id}: {vendor} ${ramount:.2f}")
    else:
        # Try amount match with wider date range (±7 days)
        date_start = date - timedelta(days=7)
        date_end = date + timedelta(days=7)
        
        cur.execute("""
            SELECT id, receipt_date, vendor_name, description, gross_amount
            FROM receipts
            WHERE ABS(gross_amount - %s) < 0.01
                AND receipt_date BETWEEN %s AND %s
                AND (mapped_bank_account_id IS NULL OR mapped_bank_account_id != %s)
            ORDER BY ABS(receipt_date - %s)
            LIMIT 3
        """, (amount, date_start, date_end, trans_id, date))
        
        receipt_matches = cur.fetchall()
        
        if receipt_matches:
            for receipt_id, receipt_date, vendor, rdesc, ramount in receipt_matches:
                date_diff = abs((receipt_date - date).days)
                match_type = f"Wide (±{date_diff}d)"
                matches.append({
                    'check_id': trans_id,
                    'check_date': date,
                    'check_amount': amount,
                    'receipt_id': receipt_id,
                    'receipt_date': receipt_date,
                    'vendor': vendor,
                    'amount_diff': abs(amount - ramount),
                    'date_diff': date_diff
                })
                print(f"{trans_id:<10} {str(date):<12} ${amount:>9.2f} {match_type:<15} {receipt_id}: {vendor} ${ramount:.2f}")
        else:
            no_match.append((trans_id, date, desc, amount))

print("\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print(f"Checks with potential matches: {len(matches)}")
print(f"Checks with no matches:        {len(no_match)}")

if matches:
    print("\n" + "=" * 120)
    print("HIGH CONFIDENCE MATCHES (±2 days)")
    print("=" * 120)
    high_conf = [m for m in matches if m['date_diff'] <= 2]
    print(f"Found {len(high_conf)} high confidence matches")
    
    total_matched = sum(m['check_amount'] for m in high_conf)
    print(f"Total amount: ${total_matched:,.2f}")
    
    print("\nDo you want to link these matches? (--write flag needed)")
    
if no_match:
    print("\n" + "=" * 120)
    print(f"CHECKS WITH NO RECEIPT MATCHES ({len(no_match)} checks)")
    print("=" * 120)
    print(f"{'Check ID':<10} {'Date':<12} {'Amount':<12} {'Description':<60}")
    print("-" * 120)
    
    no_match_total = 0
    for trans_id, date, desc, amount in no_match[:20]:  # Show first 20
        no_match_total += amount
        print(f"{trans_id:<10} {str(date):<12} ${amount:>9.2f} {desc[:60]}")
    
    if len(no_match) > 20:
        remaining = sum(c[3] for c in no_match[20:])
        print(f"... and {len(no_match)-20} more checks totaling ${remaining:,.2f}")
    
    print(f"\nTotal unmatched: ${sum(c[3] for c in no_match):,.2f}")

cur.close()
conn.close()

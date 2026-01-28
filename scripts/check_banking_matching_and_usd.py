#!/usr/bin/env python3
"""
Check banking-receipt matching status and USD purchase tracking.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("BANKING-RECEIPT MATCHING STATUS")
print("=" * 80)

# 1. Check banking transaction matching
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE debit_amount > 0
""")
total_debits = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT b.transaction_id)
    FROM banking_transactions b
    INNER JOIN banking_receipt_matching_ledger m ON b.transaction_id = m.banking_transaction_id
    WHERE b.debit_amount > 0
""")
matched_debits = cur.fetchone()[0]

unmatched_debits = total_debits - matched_debits
match_percentage = (matched_debits / total_debits * 100) if total_debits > 0 else 0

print(f"\nBANKING TRANSACTIONS (Debits):")
print(f"  Total debit transactions: {total_debits:,}")
print(f"  Matched to receipts: {matched_debits:,}")
print(f"  Unmatched: {unmatched_debits:,}")
print(f"  Match rate: {match_percentage:.1f}%")

# Show unmatched transactions
if unmatched_debits > 0:
    print(f"\n{'='*80}")
    print("UNMATCHED BANKING TRANSACTIONS (Top 50 by amount)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            b.transaction_date,
            b.debit_amount,
            b.description,
            b.vendor_extracted
        FROM banking_transactions b
        WHERE b.debit_amount > 0
          AND NOT EXISTS (
              SELECT 1 FROM banking_receipt_matching_ledger m
              WHERE m.banking_transaction_id = b.transaction_id
          )
        ORDER BY b.debit_amount DESC
        LIMIT 50
    """)
    
    unmatched = cur.fetchall()
    print(f"\n{'Date':<12} {'Amount':>12} {'Vendor':<30} {'Description'}")
    print("-" * 100)
    
    total_unmatched_amount = 0
    for date, amount, desc, vendor in unmatched:
        total_unmatched_amount += amount if amount else 0
        vendor_str = (vendor or '')[:28]
        desc_str = (desc or '')[:40]
        print(f"{date} ${amount:>10.2f} {vendor_str:<30} {desc_str}")
    
    print(f"\nTotal unmatched amount: ${total_unmatched_amount:,.2f}")

# 2. Check USD purchases
print("\n\n" + "=" * 80)
print("USD PURCHASE TRACKING")
print("=" * 80)

# Check for USD indicators in descriptions
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.vendor_name,
        r.description,
        b.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE (r.description LIKE '%USD%' 
           OR r.vendor_name LIKE '%USD%'
           OR b.description LIKE '%USD%'
           OR b.description LIKE '%INTL%'
           OR r.description LIKE '%@ 1.%')
    ORDER BY r.gross_amount DESC
    LIMIT 30
""")

usd_purchases = cur.fetchall()

print(f"\nFound {len(usd_purchases)} receipts with USD indicators")

if usd_purchases:
    print(f"\n{'Date':<12} {'Amount':>10} {'Vendor':<25} {'Description'}")
    print("-" * 100)
    
    for r_id, date, amount, vendor, r_desc, b_desc in usd_purchases:
        amt_str = f"${amount:.2f}" if amount else "$0.00"
        vendor_str = (vendor or 'UNKNOWN')[:23]
        
        # Check if conversion rate is recorded
        has_conversion = False
        if r_desc and '@ 1.' in r_desc:
            has_conversion = True
        elif b_desc and '@ 1.' in b_desc:
            has_conversion = True
        
        marker = "✅" if has_conversion else "❌"
        
        desc_to_show = r_desc or b_desc or ''
        desc_str = desc_to_show[:45]
        
        print(f"{date} {amt_str:>10} {vendor_str:<25} {marker} {desc_str}")

# Check for INTL transactions without USD marker
print("\n\n" + "=" * 80)
print("INTERNATIONAL TRANSACTIONS (INTL) WITHOUT USD MARKER")
print("=" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.vendor_name,
        r.description,
        b.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE b.description LIKE '%INTL%'
      AND r.vendor_name NOT LIKE '%USD%'
      AND r.description NOT LIKE '%USD%'
    ORDER BY r.gross_amount DESC
    LIMIT 20
""")

intl_without_usd = cur.fetchall()

if intl_without_usd:
    print(f"\nFound {len(intl_without_usd)} INTL transactions without USD marker:")
    print(f"\n{'Date':<12} {'Amount':>10} {'Vendor':<30} {'Banking Description'}")
    print("-" * 100)
    
    for r_id, date, amount, vendor, r_desc, b_desc in intl_without_usd:
        amt_str = f"${amount:.2f}" if amount else "$0.00"
        vendor_str = (vendor or 'UNKNOWN')[:28]
        b_desc_str = (b_desc or '')[:50]
        print(f"{date} {amt_str:>10} {vendor_str:<30} {b_desc_str}")

# Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"""
BANKING MATCHING:
  Match Rate: {match_percentage:.1f}%
  Unmatched Transactions: {unmatched_debits:,}
  Status: {'✅ EXCELLENT' if match_percentage > 95 else '⚠️ NEEDS WORK'}

USD TRACKING:
  USD Purchases Found: {len(usd_purchases)}
  INTL without USD marker: {len(intl_without_usd)}
  Status: {'✅ TRACKING' if len(usd_purchases) > 0 else '❌ NO USD PURCHASES FOUND'}
""")

cur.close()
conn.close()

print("\n✅ ANALYSIS COMPLETE")

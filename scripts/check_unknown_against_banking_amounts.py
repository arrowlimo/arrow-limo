#!/usr/bin/env python3
"""
Check UNKNOWN receipts against banking transactions by date+amount.
Identify if they are:
- Duplicates of already-matched banking transactions
- Unmatched banking transactions that should be linked
- Cash transactions with no banking record
"""

import psycopg2
from decimal import Decimal

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

print("=" * 80)
print("CHECKING UNKNOWN RECEIPTS AGAINST BANKING BY DATE+AMOUNT")
print("=" * 80)

cur = conn.cursor()

# Get UNKNOWN receipts with non-null amounts
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description,
        r.vendor_name
    FROM receipts r
    WHERE r.vendor_name = 'UNKNOWN'
      AND r.gross_amount IS NOT NULL
      AND r.gross_amount > 0
    ORDER BY r.gross_amount DESC
""")

unknown_receipts = cur.fetchall()
print(f"\nUNKNOWN receipts with amounts: {len(unknown_receipts)}")

# Check each against banking
duplicates = []
potential_matches = []
cash_only = []

print("\nChecking all receipts against banking...")
for i, receipt in enumerate(unknown_receipts, 1):
    if i % 100 == 0:
        print(f"  Processed {i}/{len(unknown_receipts)}...")
    receipt_id, receipt_date, gross_amount, description, vendor = receipt
    
    # Look for exact match (same date, same amount)
    cur.execute("""
        SELECT 
            b.transaction_id,
            b.transaction_date,
            b.debit_amount,
            b.description,
            b.vendor_extracted,
            m.receipt_id as matched_receipt_id
        FROM banking_transactions b
        LEFT JOIN banking_receipt_matching_ledger m ON b.transaction_id = m.banking_transaction_id
        WHERE b.transaction_date = %s
          AND ABS(b.debit_amount - %s) < 0.01
        ORDER BY b.debit_amount
    """, (receipt_date, gross_amount))
    
    banking_matches = cur.fetchall()
    
    if banking_matches:
        for match in banking_matches:
            tx_id, tx_date, debit, b_desc, b_vendor, matched_receipt = match
            
            if matched_receipt:
                # This banking transaction is already matched to another receipt
                duplicates.append({
                    'receipt': receipt,
                    'banking_tx_id': tx_id,
                    'banking_desc': b_desc,
                    'banking_vendor': b_vendor,
                    'matched_to_receipt': matched_receipt
                })
            else:
                # This banking transaction is unmatched
                potential_matches.append({
                    'receipt': receipt,
                    'banking_tx_id': tx_id,
                    'banking_desc': b_desc,
                    'banking_vendor': b_vendor
                })
    else:
        # No banking transaction found - likely cash
        cash_only.append(receipt)

print(f"\nAnalysis results:")
print(f"  Duplicates (banking already matched to another receipt): {len(duplicates)}")
print(f"  Potential matches (unmatched banking found): {len(potential_matches)}")
print(f"  Cash only (no banking transaction): {len(cash_only)}")

# Show duplicates
if duplicates:
    print("\n" + "=" * 80)
    print("DUPLICATES - Banking Already Matched to Another Receipt")
    print("=" * 80)
    print("\nDate       | Amount    | Receipt Desc        | Banking Desc            | Matched to")
    print("-" * 80)
    
    for dup in duplicates[:30]:
        r = dup['receipt']
        r_desc = (r[3] or '')[:19]
        b_desc = (dup['banking_desc'] or '')[:23]
        print(f"{r[1]} | ${r[2]:8,.2f} | {r_desc:19} | {b_desc:23} | Receipt #{dup['matched_to_receipt']}")
    
    if len(duplicates) > 30:
        print(f"\n... and {len(duplicates) - 30} more duplicates")

# Show potential matches
if potential_matches:
    print("\n" + "=" * 80)
    print("POTENTIAL MATCHES - Unmatched Banking Transactions Found")
    print("=" * 80)
    print("\nDate       | Amount    | Receipt Desc        | Banking Desc            | Banking Vendor")
    print("-" * 80)
    
    for match in potential_matches[:30]:
        r = match['receipt']
        r_desc = (r[3] or '')[:19]
        b_desc = (match['banking_desc'] or '')[:23]
        b_vendor = (match['banking_vendor'] or 'NULL')[:20]
        print(f"{r[1]} | ${r[2]:8,.2f} | {r_desc:19} | {b_desc:23} | {b_vendor}")
    
    if len(potential_matches) > 30:
        print(f"\n... and {len(potential_matches) - 30} more potential matches")

# Show cash transactions
if cash_only:
    print("\n" + "=" * 80)
    print("CASH TRANSACTIONS - No Banking Record Found")
    print("=" * 80)
    print("\nDate       | Amount    | Description")
    print("-" * 80)
    
    for r in cash_only[:30]:
        r_desc = (r[3] or '')[:50]
        print(f"{r[1]} | ${r[2]:8,.2f} | {r_desc}")
    
    if len(cash_only) > 30:
        print(f"\n... and {len(cash_only) - 30} more cash transactions")

# Summary statistics
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_unknown_amount = sum(r[2] for r in unknown_receipts if r[2])
duplicate_amount = sum(d['receipt'][2] for d in duplicates)
match_amount = sum(m['receipt'][2] for m in potential_matches)
cash_amount = sum(r[2] for r in cash_only)

print(f"\nTotal UNKNOWN receipts with amounts: {len(unknown_receipts):,}")
print(f"Total amount: ${total_unknown_amount:,.2f}")

print(f"\nDuplicates: {len(duplicates):,} receipts (${duplicate_amount:,.2f})")
print(f"  ⚠️  These receipts duplicate banking already matched elsewhere")
print(f"  Recommendation: DELETE these receipt records")

print(f"\nPotential matches: {len(potential_matches):,} receipts (${match_amount:,.2f})")
print(f"  ✅ Banking transactions exist but aren't matched")
print(f"  Recommendation: MATCH these to banking and extract vendor from banking description")

print(f"\nCash transactions: {len(cash_only):,} receipts (${cash_amount:,.2f})")
print(f"  💵 No banking record found - likely cash payments")
print(f"  Recommendation: Extract vendor from receipt description, keep as cash")

# Check NULL/zero amount receipts
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND (gross_amount IS NULL OR gross_amount = 0)
""")
null_count, null_sum = cur.fetchone()
print(f"\nNULL/zero amounts: {null_count:,} receipts")
print(f"  Recommendation: DELETE these (likely journal entries/placeholders)")

print("\n" + "=" * 80)
print("ACTION PLAN")
print("=" * 80)
print(f"\n1. DELETE {len(duplicates):,} duplicate receipts (${duplicate_amount:,.2f})")
print(f"2. DELETE {null_count:,} NULL/zero amount receipts")
print(f"3. MATCH {len(potential_matches):,} receipts to banking (${match_amount:,.2f})")
print(f"4. EXTRACT vendors for {len(cash_only):,} cash receipts (${cash_amount:,.2f})")

cur.close()
conn.close()

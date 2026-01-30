#!/usr/bin/env python3
"""
Audit UNKNOWN receipt vendors by checking linked banking transactions.
- If linked to banking: Extract vendor from banking description
- If from QuickBooks only: Flag as potentially bogus/cash
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

print("=" * 80)
print("AUDITING UNKNOWN RECEIPTS AGAINST BANKING MATCHES")
print("=" * 80)

cur = conn.cursor()

# Get UNKNOWN receipts with banking match info
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description as receipt_desc,
        r.vendor_name,
        r.source_system,
        b.transaction_id,
        b.transaction_date,
        b.description as banking_desc,
        b.vendor_extracted,
        b.debit_amount,
        b.credit_amount
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'UNKNOWN'
    ORDER BY r.gross_amount DESC
""")

unknown_receipts = cur.fetchall()

print(f"\nTotal UNKNOWN receipts: {len(unknown_receipts)}")

# Categorize by source
from_banking = []
from_quickbooks = []
vendor_extractable = []

for receipt in unknown_receipts:
    (receipt_id, receipt_date, gross_amount, receipt_desc, vendor_name, 
     source_system, banking_tx_id, tx_date, banking_desc, banking_vendor, 
     debit, credit) = receipt
    
    if banking_tx_id is None:
        from_quickbooks.append(receipt)
    else:
        from_banking.append(receipt)
        
        # Check if we can extract vendor from banking description
        if banking_desc:
            # Try to extract meaningful vendor info
            if any(keyword in banking_desc.upper() for keyword in 
                   ['HEFFNER', 'SQUARE', 'TELUS', 'SHAW', 'ROGERS', 
                    'ESSO', 'SHELL', 'PETRO', 'CO-OP', 'FAS GAS',
                    'WALMART', 'SAFEWAY', 'SOBEYS', 'COSTCO',
                    'LIQUOR', 'TIM HORTONS', 'CANADIAN TIRE']):
                vendor_extractable.append(receipt)

print(f"\nSource breakdown:")
print(f"  Linked to banking: {len(from_banking)}")
print(f"  QuickBooks only (potentially bogus): {len(from_quickbooks)}")
print(f"  Vendor extractable from banking: {len(vendor_extractable)}")

# Show banking-linked UNKNOWN with descriptions
print("\n" + "=" * 80)
print("BANKING-LINKED UNKNOWN RECEIPTS (Top 50)")
print("=" * 80)
print("\nDate       | Amount    | Receipt Desc              | Banking Description")
print("-" * 80)

for receipt in from_banking[:50]:
    (receipt_id, receipt_date, gross_amount, receipt_desc, vendor_name, 
     source_system, banking_tx_id, tx_date, banking_desc, banking_vendor, 
     debit, credit) = receipt
    
    r_desc = (receipt_desc or '')[:25]
    b_desc = (banking_desc or '')[:45]
    print(f"{receipt_date} | ${gross_amount:8,.2f} | {r_desc:25} | {b_desc}")

# Show QuickBooks-only UNKNOWN (potentially bogus)
print("\n" + "=" * 80)
print("QUICKBOOKS-ONLY UNKNOWN RECEIPTS (Potentially Bogus)")
print("=" * 80)
print("\nDate       | Amount    | Source       | Description")
print("-" * 80)

total_qb_amount = 0
for receipt in from_quickbooks[:50]:
    (receipt_id, receipt_date, gross_amount, receipt_desc, vendor_name, 
     source_system, banking_tx_id, tx_date, banking_desc, banking_vendor, 
     debit, credit) = receipt
    
    r_desc = (receipt_desc or '')[:50]
    src = source_system or 'UNKNOWN'
    amt = gross_amount or 0.0
    print(f"{receipt_date} | ${amt:8,.2f} | {src:12} | {r_desc}")
    total_qb_amount += amt

if len(from_quickbooks) > 50:
    print(f"\n... and {len(from_quickbooks) - 50} more")

total_qb_amount = sum(r[2] or 0.0 for r in from_quickbooks)
print(f"\nTotal QuickBooks-only UNKNOWN amount: ${total_qb_amount:,.2f}")

# Show vendor-extractable examples
print("\n" + "=" * 80)
print("VENDOR EXTRACTABLE FROM BANKING (Examples)")
print("=" * 80)

if vendor_extractable:
    print("\nReceipt Date | Amount    | Banking Description")
    print("-" * 80)
    for receipt in vendor_extractable[:20]:
        (receipt_id, receipt_date, gross_amount, receipt_desc, vendor_name, 
         source_system, banking_tx_id, tx_date, banking_desc, banking_vendor, 
         debit, credit) = receipt
        
        b_desc = (banking_desc or '')[:65]
        print(f"{receipt_date} | ${gross_amount:8,.2f} | {b_desc}")
    
    if len(vendor_extractable) > 20:
        print(f"\n... and {len(vendor_extractable) - 20} more")
else:
    print("\nNone found - all banking descriptions too generic")

# Summary
print("\n" + "=" * 80)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 80)

print(f"\nTotal UNKNOWN receipts: {len(unknown_receipts):,}")
print(f"  • Linked to banking: {len(from_banking):,} (can extract vendor from banking description)")
print(f"  • QuickBooks only: {len(from_quickbooks):,} (⚠️  potentially cash/bogus - no banking match)")
print(f"  • Vendor extractable: {len(vendor_extractable):,} (vendor name visible in banking desc)")

if from_quickbooks:
    print(f"\n⚠️  WARNING: {len(from_quickbooks)} UNKNOWN receipts from QuickBooks with no banking match")
    print(f"   Total amount: ${sum(r[2] for r in from_quickbooks):,.2f}")
    print(f"   These may be:")
    print(f"   - Cash transactions (legitimate)")
    print(f"   - Data entry errors (bogus)")
    print(f"   - Unmatched banking transactions (need reconciliation)")

if vendor_extractable:
    print(f"\n✅ Can extract vendors for {len(vendor_extractable)} receipts from banking descriptions")

print("\nNext steps:")
print("  1. Extract vendors from banking descriptions for matched receipts")
print("  2. Review QuickBooks-only receipts for legitimacy")
print("  3. Flag potential bogus entries for manual review")

cur.close()
conn.close()

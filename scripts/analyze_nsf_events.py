#!/usr/bin/env python3
"""
Analyze NSF events - these are customer checks that bounced, not company expenses.
NSF events should be tracked as customer account issues, not matched to company checks.
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
print("ANALYZING NSF EVENT RECEIPTS")
print("=" * 100)

# Find NSF receipts that were created
cur.execute('''
    SELECT id, receipt_date, gross_amount, description, vendor_name, mapped_bank_account_id
    FROM receipts
    WHERE document_type = 'NSF_EVENT'
        AND EXTRACT(YEAR FROM receipt_date) = 2012
    ORDER BY receipt_date
''')

nsf_receipts = cur.fetchall()
print(f'\nFound {len(nsf_receipts)} NSF event receipts in 2012:')
print()
print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Bank ID':<10} {'Description':<50}")
print("-" * 100)

for id, date, amount, desc, vendor, bank_id in nsf_receipts:
    vendor_str = vendor if vendor else "(none)"
    print(f"{id:<8} {str(date):<12} ${amount:>9,.2f} {str(bank_id):<10} {desc[:50]}")

total = sum(r[2] for r in nsf_receipts)
print(f'\nTotal NSF amount: ${total:,.2f}')

print("\n" + "=" * 100)
print("UNDERSTANDING NSF EVENTS")
print("=" * 100)
print("""
NSF (Non-Sufficient Funds) events represent:
  - Customer checks that BOUNCED due to insufficient funds
  - Money that was REVERSED by the bank (debited back out)
  - Customer account issues requiring follow-up
  
NSF events should NOT be:
  - Matched to company outgoing checks (those are expenses)
  - Treated as company expenses (they're reversed customer payments)
  - Linked to vendor receipts

NSF events SHOULD be:
  - Tracked as customer payment failures
  - Linked to customer accounts for collections
  - Noted as accounts receivable issues
  - Used to flag problematic customers
""")

# Find banking transactions with NSF in description
print("\n" + "=" * 100)
print("BANKING TRANSACTIONS WITH NSF REVERSALS")
print("=" * 100)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.debit_amount,
        bt.description,
        CASE 
            WHEN r.id IS NOT NULL THEN 'Has receipt'
            ELSE 'No receipt'
        END as status
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.mapped_bank_account_id = bt.transaction_id
    WHERE bt.account_number = '903990106011'
        AND EXTRACT(YEAR FROM bt.transaction_date) = 2012
        AND bt.description ILIKE '%NSF%'
        AND bt.debit_amount > 0
    ORDER BY bt.transaction_date
""")

nsf_bank = cur.fetchall()
print(f"\nFound {len(nsf_bank)} banking transactions with NSF:")
print()
print(f"{'Trans ID':<10} {'Date':<12} {'Amount':<12} {'Status':<15} {'Description':<50}")
print("-" * 100)

for trans_id, date, amount, desc, status in nsf_bank:
    print(f"{trans_id:<10} {str(date):<12} ${amount:>9,.2f} {status:<15} {desc[:50]}")

nsf_bank_total = sum(r[2] for r in nsf_bank)
print(f"\nTotal NSF reversals: ${nsf_bank_total:,.2f}")

# Check if NSF receipts properly linked
linked = sum(1 for r in nsf_receipts if r[5] is not None)
print(f"\n{'='*100}")
print(f"NSF receipts linked to banking: {linked}/{len(nsf_receipts)}")
print(f"NSF receipts NOT linked:        {len(nsf_receipts) - linked}/{len(nsf_receipts)}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("RECOMMENDATION")
print("=" * 100)
print("""
NSF receipts should be categorized differently:
  - Category: 'Customer NSF' (not expense category)
  - Document type: 'NSF_REVERSAL' or 'CUSTOMER_NSF'
  - Vendor: Customer name (not 'NSF Event')
  - Description: 'Customer check returned NSF - [check details]'
  
This allows tracking which customers have NSF issues for collections.
""")

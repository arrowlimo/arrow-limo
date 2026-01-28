import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("CHECKING BANKING DESCRIPTIONS vs RECEIPT VENDOR NAMES")
print("="*100)

# Check cash withdrawals in banking
cur.execute("""
    SELECT description, debit_amount, transaction_date, transaction_id
    FROM banking_transactions 
    WHERE description ILIKE '%CASH WITHDRAWAL%'
    ORDER BY debit_amount DESC 
    LIMIT 30
""")

print("\n1. ACTUAL BANKING CASH WITHDRAWALS:")
print("-"*100)

banking_cash = cur.fetchall()
cash_tx_ids = set()

for desc, amt, date, tx_id in banking_cash:
    cash_tx_ids.add(tx_id)
    print(f"${float(amt) if amt else 0:>10,.2f} | {date} | {desc[:70]}")

print(f"\nFound {len(banking_cash)} cash withdrawal banking transactions")

# Now check what receipts are linked to these
print(f"\n2. RECEIPTS LINKED TO CASH WITHDRAWAL BANKING TRANSACTIONS:")
print("-"*100)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        r.gross_amount,
        bt.description,
        bt.transaction_date
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description ILIKE '%CASH WITHDRAWAL%'
      AND r.exclude_from_reports = FALSE
    ORDER BY r.gross_amount DESC
""")

cash_receipts = cur.fetchall()

print(f"Found {len(cash_receipts)} receipts linked to cash withdrawals\n")

# Categorize by vendor name
already_correct = []
paul_richard_contaminated = []
other_contaminated = []

for receipt_id, vendor, amount, banking, date in cash_receipts:
    if vendor == 'CASH WITHDRAWAL':
        already_correct.append((receipt_id, vendor, amount))
    elif 'Paul Richard' in vendor:
        paul_richard_contaminated.append((receipt_id, vendor, amount, banking))
    else:
        other_contaminated.append((receipt_id, vendor, amount, banking))

print(f"CATEGORIZATION:")
print(f"  Already correct (vendor = 'CASH WITHDRAWAL'): {len(already_correct)} receipts")
print(f"  Contaminated with 'Paul Richard': {len(paul_richard_contaminated)} receipts")
print(f"  Other contamination: {len(other_contaminated)} receipts")

if paul_richard_contaminated:
    print(f"\n3. PAUL RICHARD CONTAMINATION (banking says CASH, receipt says Paul):")
    print("-"*100)
    total_paul_contamination = sum(float(x[2]) for x in paul_richard_contaminated)
    
    for receipt_id, vendor, amount, banking in paul_richard_contaminated[:20]:
        print(f"Receipt {receipt_id} | ${float(amount):>10,.2f}")
        print(f"  Receipt vendor: {vendor}")
        print(f"  Banking desc:   {banking[:70]}")
        print()
    
    if len(paul_richard_contaminated) > 20:
        print(f"  ... and {len(paul_richard_contaminated) - 20} more")
    
    print(f"\nTOTAL PAUL CONTAMINATION: ${total_paul_contamination:,.2f}")

if other_contaminated:
    print(f"\n4. OTHER VENDOR CONTAMINATION:")
    print("-"*100)
    total_other = sum(float(x[2]) for x in other_contaminated)
    
    for receipt_id, vendor, amount, banking in other_contaminated[:20]:
        print(f"Receipt {receipt_id} | ${float(amount):>10,.2f}")
        print(f"  Receipt vendor: {vendor}")
        print(f"  Banking desc:   {banking[:70]}")
        print()
    
    print(f"\nTOTAL OTHER CONTAMINATION: ${total_other:,.2f}")

print(f"\n{'='*100}")
print(f"ACTION REQUIRED:")
print(f"{'='*100}")
if paul_richard_contaminated or other_contaminated:
    total_to_fix = len(paul_richard_contaminated) + len(other_contaminated)
    total_amount = sum(float(x[2]) for x in paul_richard_contaminated) + sum(float(x[2]) for x in other_contaminated)
    print(f"""
{total_to_fix} receipts (${total_amount:,.2f}) are mislabeled:
  - Banking says: CASH WITHDRAWAL
  - Receipt says: Paul Richard / other vendor names

These should ALL be updated to vendor_name = 'CASH WITHDRAWAL'
""")
else:
    print("\n✅ All cash withdrawal receipts are correctly labeled!")

cur.close()
conn.close()

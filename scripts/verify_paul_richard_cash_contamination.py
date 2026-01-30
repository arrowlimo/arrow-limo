import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("CRITICAL: PAUL RICHARD vs CASH WITHDRAWAL CROSS-CHECK")
print("="*100)

# Check "Cheque Expense - Paul Richard" against banking descriptions
cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        r.gross_amount,
        r.receipt_date,
        bt.description,
        bt.debit_amount
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE '%Paul Richard%'
      AND r.exclude_from_reports = FALSE
    ORDER BY r.gross_amount DESC
""")

paul_receipts = cur.fetchall()
print(f"Found {len(paul_receipts)} receipts with 'Paul Richard' in vendor name\n")

# Categorize by banking description
cash_withdrawals = []
actual_paul_payments = []
no_banking_link = []

for receipt_id, vendor, amount, date, banking_desc, bank_debit in paul_receipts:
    if banking_desc:
        if 'CASH WITHDRAWAL' in banking_desc.upper() or 'ATM' in banking_desc.upper():
            cash_withdrawals.append((receipt_id, vendor, amount, date, banking_desc))
        else:
            actual_paul_payments.append((receipt_id, vendor, amount, date, banking_desc))
    else:
        no_banking_link.append((receipt_id, vendor, amount, date))

print(f"CATEGORIZATION:")
print(f"  CASH WITHDRAWALS (QuickBooks mislabeled): {len(cash_withdrawals)} receipts")
print(f"  ACTUAL Paul Richard payments: {len(actual_paul_payments)} receipts")
print(f"  No banking link: {len(no_banking_link)} receipts")
print()

# Show cash withdrawals
if cash_withdrawals:
    print(f"\n{'='*100}")
    print(f"CASH WITHDRAWALS MISLABELED AS 'Paul Richard' ({len(cash_withdrawals)} receipts):")
    print(f"{'='*100}\n")
    
    total_mislabeled = sum(float(x[2]) for x in cash_withdrawals)
    
    for receipt_id, vendor, amount, date, banking_desc in cash_withdrawals[:30]:
        print(f"Receipt {receipt_id} | ${float(amount):>10,.2f} | {date}")
        print(f"  QB Vendor: {vendor}")
        print(f"  Banking:   {banking_desc[:80]}")
        print()
    
    if len(cash_withdrawals) > 30:
        print(f"  ... and {len(cash_withdrawals) - 30} more")
    
    print(f"\nTOTAL MISLABELED: ${total_mislabeled:,.2f}")

# Show actual Paul Richard payments
if actual_paul_payments:
    print(f"\n{'='*100}")
    print(f"ACTUAL Paul Richard Payments ({len(actual_paul_payments)} receipts):")
    print(f"{'='*100}\n")
    
    total_actual = sum(float(x[2]) for x in actual_paul_payments)
    
    for receipt_id, vendor, amount, date, banking_desc in actual_paul_payments[:20]:
        print(f"Receipt {receipt_id} | ${float(amount):>10,.2f} | {date}")
        print(f"  QB Vendor: {vendor}")
        print(f"  Banking:   {banking_desc[:80]}")
        print()
    
    if len(actual_paul_payments) > 20:
        print(f"  ... and {len(actual_paul_payments) - 20} more")
    
    print(f"\nTOTAL ACTUAL: ${total_actual:,.2f}")

# Check all "Cheque Expense - [vendor]" for cash withdrawal contamination
print(f"\n{'='*100}")
print(f"CHECKING ALL 'Cheque Expense' ENTRIES FOR CASH WITHDRAWAL CONTAMINATION:")
print(f"{'='*100}\n")

cur.execute("""
    SELECT 
        r.vendor_name,
        COUNT(*) as count,
        SUM(CASE WHEN bt.description ILIKE '%CASH WITHDRAWAL%' OR bt.description ILIKE '%ATM%' THEN 1 ELSE 0 END) as cash_count,
        SUM(r.gross_amount) as total_amount,
        SUM(CASE WHEN bt.description ILIKE '%CASH WITHDRAWAL%' OR bt.description ILIKE '%ATM%' THEN r.gross_amount ELSE 0 END) as cash_amount
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE 'Cheque Expense -%'
      AND r.exclude_from_reports = FALSE
    GROUP BY r.vendor_name
    HAVING SUM(CASE WHEN bt.description ILIKE '%CASH WITHDRAWAL%' OR bt.description ILIKE '%ATM%' THEN 1 ELSE 0 END) > 0
    ORDER BY SUM(CASE WHEN bt.description ILIKE '%CASH WITHDRAWAL%' OR bt.description ILIKE '%ATM%' THEN r.gross_amount ELSE 0 END) DESC
""")

contaminated_vendors = cur.fetchall()

print(f"QB Vendor Name                                          | Total | Cash | Total Amount | Cash Amount")
print(f"-"*100)

total_contamination = 0
for vendor, total_count, cash_count, total_amt, cash_amt in contaminated_vendors:
    total_contamination += float(cash_amt) if cash_amt else 0
    extracted_vendor = vendor.split(' - ', 1)[1] if ' - ' in vendor else vendor
    print(f"{extracted_vendor[:50]:<50} | {total_count:>5} | {cash_count:>4} | ${float(total_amt):>11,.2f} | ${float(cash_amt):>11,.2f}")

print(f"\n{'='*100}")
print(f"TOTAL CASH WITHDRAWAL CONTAMINATION: ${total_contamination:,.2f}")
print(f"These should be vendor_name = 'CASH WITHDRAWAL', NOT the QB vendor name")
print(f"{'='*100}")

# Summary
print(f"\n{'='*100}")
print(f"EXTRACTION STRATEGY:")
print(f"{'='*100}")
print(f"""
1. Before extracting vendor from "Cheque Expense - [vendor]":
   → Check banking_transactions.description
   → If contains "CASH WITHDRAWAL" or "ATM", set vendor = 'CASH WITHDRAWAL'
   → Otherwise extract vendor name after ' - '

2. Current contamination:
   → {len(cash_withdrawals)} receipts labeled "Paul Richard" are actually cash withdrawals
   → ${total_mislabeled:,.2f} mislabeled
   → Total QB contamination: ${total_contamination:,.2f}

3. Actual legitimate payments:
   → {len(actual_paul_payments)} receipts to Paul Richard (verified with banking)
   → ${total_actual:,.2f} in real payments

This explains why QuickBooks is USELESS - it systematically mislabeled cash withdrawals!
""")

cur.close()
conn.close()

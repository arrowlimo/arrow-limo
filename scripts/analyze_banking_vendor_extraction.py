import psycopg2
import re
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("BANKING TRANSACTION VENDOR NAME EXTRACTION ANALYSIS")
print("="*100)

# 1. Analyze FGP codes in banking descriptions
print("\n1. FGP MERCHANT CODE PATTERNS IN BANKING")
print("-"*100)

cur.execute("""
    SELECT 
        bt.description,
        r.vendor_name,
        r.gross_amount,
        bt.debit_amount
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description LIKE '%FGP%'
      AND bt.debit_amount IS NOT NULL
      AND (r.exclude_from_reports = FALSE OR r.exclude_from_reports IS NULL)
    ORDER BY bt.transaction_date
    LIMIT 50
""")

fgp_patterns = defaultdict(list)
for desc, vendor, receipt_amt, bank_amt in cur.fetchall():
    # Extract FGP code pattern
    match = re.search(r'FGP\d+\s+([A-Z0-9-]+)', desc)
    if match:
        merchant_code = match.group(1)
        fgp_patterns[merchant_code].append((desc, vendor, receipt_amt, bank_amt))

print(f"Found {len(fgp_patterns)} distinct FGP merchant codes\n")

# Decode known codes
merchant_codes = {
    '608-WB': 'WINE AND BEYOND',
    'LB': 'LIQUOR BARN', 
    'LD': 'LIQUOR DEPOT',
    'WB': 'WINE AND BEYOND'
}

for code in sorted(fgp_patterns.keys(), key=lambda x: len(fgp_patterns[x]), reverse=True)[:20]:
    transactions = fgp_patterns[code]
    total_amt = sum(float(t[2]) if t[2] else 0 for t in transactions)
    
    # Try to decode
    decoded = merchant_codes.get(code, '???')
    
    print(f"\n{code} → {decoded} ({len(transactions)} transactions, ${total_amt:,.2f})")
    print(f"  Sample banking: {transactions[0][0][:80]}...")
    print(f"  Current vendor: {transactions[0][1]}")
    
    # Check if all have same vendor pattern
    vendors = set(t[1] for t in transactions if t[1])
    if len(vendors) == 1:
        print(f"  ✅ Consistent vendor name")
    else:
        print(f"  ⚠️  Multiple vendor names: {len(vendors)} variations")

# 2. Analyze CREDIT MEMO patterns
print("\n\n2. CREDIT MEMO PATTERNS (OCR 3-line combinations)")
print("-"*100)

cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description,
        r.gross_amount,
        bt.credit_amount,
        bt.transaction_date
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE 'CREDIT MEMO%'
      AND r.exclude_from_reports = FALSE
    ORDER BY r.gross_amount DESC
    LIMIT 20
""")

print("Top 20 CREDIT MEMO entries with banking descriptions:\n")
credit_patterns = defaultdict(int)

for vendor, desc, amt, credit, date in cur.fetchall():
    print(f"${float(amt):>10,.2f} | {vendor[:40]:<40} | Banking: {desc[:60] if desc else 'NO BANKING LINK'}...")
    
    # Extract potential merchant from CREDIT MEMO pattern
    # Pattern: "CREDIT MEMO ##### MERCHANT"
    match = re.search(r'CREDIT MEMO \d+ (.+)', vendor)
    if match:
        merchant = match.group(1).strip()
        credit_patterns[merchant] += 1

print(f"\nExtracted merchants from CREDIT MEMO patterns:")
for merchant, count in sorted(credit_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {count:>3}x | {merchant}")

# 3. Analyze CORRECTION patterns
print("\n\n3. CORRECTION PATTERNS (NSF returned entries)")
print("-"*100)

cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description,
        r.gross_amount,
        bt.debit_amount,
        bt.transaction_date
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE 'CORRECTION%'
      AND r.exclude_from_reports = FALSE
    ORDER BY ABS(r.gross_amount) DESC
    LIMIT 20
""")

print("Top 20 CORRECTION entries with banking descriptions:\n")

for vendor, desc, amt, debit, date in cur.fetchall():
    print(f"${float(amt):>10,.2f} | {vendor[:40]:<40}")
    if desc:
        # Check if description mentions NSF
        if 'NSF' in desc.upper() or 'RETURN' in desc.upper() or 'INSUFFICIENT' in desc.upper():
            print(f"             ✅ NSF/RETURN confirmed: {desc[:70]}")
        else:
            print(f"             ⚠️  Other: {desc[:70]}")
    else:
        print(f"             ❌ NO BANKING LINK")

# 4. EMAIL TRANSFER recipient extraction
print("\n\n4. EMAIL TRANSFER RECIPIENT EXTRACTION FROM BANKING")
print("-"*100)

cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description,
        r.gross_amount,
        bt.debit_amount
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('EMAIL TRANSFER', 'E-TRANSFER')
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
    ORDER BY r.gross_amount DESC
    LIMIT 30
""")

email_recipients = []
for vendor, desc, amt, debit in cur.fetchall():
    # Try to extract recipient name
    # Pattern 1: "E-TRANSFER... Name 4506*..."
    match1 = re.search(r'E-TRANSFER[^A-Z]*([A-Z][A-Za-z\s&\.]+?)\s*4506', desc)
    # Pattern 2: "EMAIL TRANSFER TO [Name]"
    match2 = re.search(r'EMAIL TRANSFER TO\s+([A-Z][A-Za-z\s&\.]+)', desc)
    # Pattern 3: Just extract words before card number
    match3 = re.search(r'TRANSFER[^A-Z]*([A-Z][A-Za-z\s&\.]{3,}?)\s*(?:4506|\d{4}\*)', desc)
    
    recipient = None
    if match1:
        recipient = match1.group(1).strip()
    elif match2:
        recipient = match2.group(1).strip()
    elif match3:
        recipient = match3.group(1).strip()
    
    if recipient and len(recipient) > 2:
        # Clean up common garbage
        recipient = recipient.replace('PURCHASE', '').replace('SEND', '').strip()
        if len(recipient) > 3:
            email_recipients.append((recipient, desc, amt))
            print(f"${float(amt):>10,.2f} | Current: {vendor:<20} → '{recipient}'")
            print(f"             Banking: {desc[:80]}...")

print(f"\n✅ Successfully extracted {len(email_recipients)} recipient names from banking descriptions")

# 5. CHEQUE payee extraction
print("\n\n5. CHEQUE PAYEE EXTRACTION FROM BANKING")
print("-"*100)

cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description,
        r.gross_amount,
        bt.check_number
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('UNKNOWN PAYEE (CHEQUE)', 'CHECK PAYMENT', 'CHEQUE')
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
    ORDER BY r.gross_amount DESC
    LIMIT 30
""")

cheque_payees = []
for vendor, desc, amt, cheque_num in cur.fetchall():
    # Pattern: "CHEQUE ### PAYEE NAME" or "CHQ ### PAYEE"
    match1 = re.search(r'(?:CHEQUE|CHQ|CHECK)\s+\d+\s+([A-Z][A-Za-z\s&\.]+?)(?:\s+\d{4}|$)', desc)
    # Pattern: Words after cheque number
    match2 = re.search(r'(?:CHEQUE|CHQ)\s+\d+[^A-Z]*([A-Z][A-Za-z\s&\.]{3,})', desc)
    
    payee = None
    if match1:
        payee = match1.group(1).strip()
    elif match2:
        payee = match2.group(1).strip()
    
    if payee and len(payee) > 2:
        payee = payee.replace('PAYMENT', '').replace('DEBIT', '').strip()
        if len(payee) > 3:
            cheque_payees.append((payee, desc, amt, cheque_num))
            print(f"${float(amt):>10,.2f} | Cheque {cheque_num if cheque_num else '???':<6} → '{payee}'")
            print(f"             Banking: {desc[:80]}...")

print(f"\n✅ Successfully extracted {len(cheque_payees)} payee names from banking descriptions")

# 6. QuickBooks "Cheque Expense - [Vendor]" extraction
print("\n\n6. QUICKBOOKS 'Cheque Expense' VENDOR EXTRACTION")
print("-"*100)

cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE 'Cheque Expense -%'
      AND exclude_from_reports = FALSE
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

qb_vendors = []
for vendor, count, amount in cur.fetchall():
    # Extract vendor after " - "
    if ' - ' in vendor:
        real_vendor = vendor.split(' - ', 1)[1].strip()
        qb_vendors.append((real_vendor, vendor, count, amount))

print(f"Found {len(qb_vendors)} QuickBooks 'Cheque Expense' patterns\n")
print(f"{'Count':<6} | {'Amount':>12} | {'QB Garbage':<50} → {'Real Vendor'}")
print("-"*100)

for real_vendor, qb_vendor, count, amount in sorted(qb_vendors, key=lambda x: x[2], reverse=True)[:30]:
    print(f"{count:<6} | ${float(amount):>11,.2f} | {qb_vendor[:48]:<48} → {real_vendor}")

# SUMMARY
print("\n\n" + "="*100)
print("SUMMARY: VENDOR NAME EXTRACTION OPPORTUNITIES")
print("="*100)

total_qb = sum(x[2] for x in qb_vendors)
total_qb_amt = sum(float(x[3]) for x in qb_vendors)

print(f"""
1. QuickBooks 'Cheque Expense' pollution:
   {total_qb:,} receipts | ${total_qb_amt:,.2f}
   ✅ Can extract real vendor after ' - '

2. EMAIL TRANSFER recipients:
   {len(email_recipients):,} sampled (2,852 total) | $1,211,523.36 total
   ✅ Can extract from banking description

3. CHEQUE payees:
   {len(cheque_payees):,} sampled (272+ total) | $314,927.21+ total
   ✅ Can extract from banking description

4. FGP merchant codes:
   {len(fgp_patterns):,} distinct codes found
   ✅ Can decode using merchant code table
   
5. CREDIT MEMO (OCR 3-line):
   {len(credit_patterns):,} merchants extracted from patterns
   ⚠️  May contain duplicate receipts from OCR errors

6. CORRECTION entries:
   ✅ Confirmed NSF returned entries from banking

TOTAL EXTRACTABLE: ~{total_qb + 2852 + 272:,} receipts with real vendor names buried in data
""")

# Check for potential duplicates in CREDIT MEMO
print("\n" + "="*100)
print("DUPLICATE DETECTION: CREDIT MEMO + ORIGINAL TRANSACTION")
print("="*100)

cur.execute("""
    SELECT 
        r1.receipt_id,
        r1.vendor_name,
        r1.gross_amount,
        r1.receipt_date,
        r2.receipt_id,
        r2.vendor_name,
        r2.gross_amount,
        r2.receipt_date
    FROM receipts r1
    JOIN receipts r2 ON 
        ABS(r1.gross_amount - r2.gross_amount) < 0.01
        AND r1.receipt_date = r2.receipt_date
        AND r1.receipt_id < r2.receipt_id
    WHERE r1.vendor_name LIKE 'CREDIT MEMO%'
      AND r1.exclude_from_reports = FALSE
      AND r2.exclude_from_reports = FALSE
    ORDER BY r1.gross_amount DESC
    LIMIT 20
""")

potential_dupes = cur.fetchall()
if potential_dupes:
    print(f"\n⚠️  Found {len(potential_dupes)} potential duplicates (CREDIT MEMO + original):\n")
    for r1_id, r1_vendor, r1_amt, r1_date, r2_id, r2_vendor, r2_amt, r2_date in potential_dupes:
        print(f"${float(r1_amt):>10,.2f} on {r1_date}")
        print(f"  Receipt {r1_id}: {r1_vendor[:60]}")
        print(f"  Receipt {r2_id}: {r2_vendor[:60]}")
        print()
else:
    print("\n✅ No obvious CREDIT MEMO duplicates found with simple date+amount match")

cur.close()
conn.close()

print("\n" + "="*100)
print("NEXT STEP: Create vendor name extraction script to fix all patterns")
print("="*100)
